from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, authenticate
from django.contrib.auth.decorators import login_required
from .models import Usuario, PerfilDermatologico
import requests
import json
import time


YOUCAM_URL = 'https://yce-api-01.makeupar.com/s2s/v2.1/task/skin-analysis' # link para conectar a api
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "  "  # token de acesso api
}

def comunicar_youcam_api(foto_arquivo): #envia a foto para a api e recebe o resultado
    dados_config = {
        "dst_actions": json.dumps([                             #pontos que a ia vai verificar e devolver
            "acne", "eye_bag", "moisture", "pore", "redness",
            "texture", "skin_type", "dark_circle_v2", "oiliness",
            "radiance", "age_spot"
        ]),
        "miniserver_args": json.dumps({"enable_mask_overlay": True}),
        "format": "json",       #formato de retorno
        "pf_camera_kit": "False"
    }

    files = {  #prepara a foto para envio
        'src_file': (foto_arquivo.name, foto_arquivo.read(), foto_arquivo.content_type)
    }

    try:
        resposta = requests.post(YOUCAM_URL, headers=HEADERS, data=dados_config, files=files, timeout=15)
        if not resposta.ok:
            return None

        task_id = resposta.json().get('data', {}).get('task_id')
        if not task_id:
            return None

        for _ in range(15):
            time.sleep(2)
            checagem = requests.get(f"{YOUCAM_URL}/{task_id}", headers=HEADERS, timeout=10)

            if checagem.ok:
                payload = checagem.json()
                status = payload.get('data', {}).get('task_status')

                if status == 'success':
                    return payload.get('data', {}).get('results')
                elif status == 'error':
                    break
    except Exception as e:
        print(f"[Erro YouCam API]: {e}")

    return None


#calculo da porcentagem de saude da pele
PESO_FOTOTIPO = 0.40
PESO_TIPO_PELE = 0.30
PESO_MAQUIAGEM = 0.15
PESO_ALERGIA = 0.15

# Nota de 0 a 100 pra cada resposta possivel
NOTAS_FOTOTIPO = {
    1: 20,   # sempre queima, nunca bronzeia == pouca protecao natural contra UV
    2: 45,   # sempre queima, bronzeia pouco
    3: 75,   # queima moderado, bronzeia gradualmente
    4: 100,  # raramente queima == mais protecao natural contra UV
}

NOTAS_TIPO_PELE = {
    'normal': 100,  # pele equilibrada
    'mista': 75,    # duas tendencias ao mesmo tempo (oleosa na zona T, seca nas bochechas)
    'seca': 60,     # barreira cutanea mais fragil, mais sensivel a irritacao
    'oleosa': 55,   # mais producao de sebo, mais tendencia a cravos e acne
}

NOTA_MAQUIAGEM_SIM = 50
NOTA_MAQUIAGEM_NAO = 100

NOTA_ALERGIA_SIM = 60
NOTA_ALERGIA_NAO = 100


def calcular_porcentagem_saude(tipo_pele, fototipo, usa_maquiagem, tem_alergia):
    # calcula o score so com as respostas do questionario (sem depender da ia)
    nota_fototipo = NOTAS_FOTOTIPO.get(fototipo, 70)
    nota_tipo_pele = NOTAS_TIPO_PELE.get(tipo_pele, 70)
    nota_maquiagem = NOTA_MAQUIAGEM_SIM if usa_maquiagem == 'sim' else NOTA_MAQUIAGEM_NAO
    nota_alergia = NOTA_ALERGIA_SIM if tem_alergia == '1' else NOTA_ALERGIA_NAO

    score = (
        nota_fototipo * PESO_FOTOTIPO +
        nota_tipo_pele * PESO_TIPO_PELE +
        nota_maquiagem * PESO_MAQUIAGEM +
        nota_alergia * PESO_ALERGIA
    )

    return round(score)


def tela_cadastro(request):

    # verifica se o navegador está enviando dados através de um formulário (POST)
    if request.method == "POST":
        nome = request.POST.get('nome')
        email = request.POST.get('email')
        senha = request.POST.get('senha') 
        
        # cria e salva um novo registro na tabela usuario, já com a senha criptografada
        novo_usuario = Usuario.objects.create_user(
            email=email,
            nome_usuario=nome,
            password=senha,
        )

        # faz o login automático e manda o usuário para a tela do questionário
        auth_login(request, novo_usuario)
        return redirect('questionario')
        
        # se a requisição NÃO for POST, exibe a tela com o formulário de cadastro limpo.
    return render(request, 'core/cadastro.html')


def tela_questionario(request):
    if request.method == "POST":
        # pega as respostas do questionario
        idade = request.POST.get('idade')
        tipo_pele = request.POST.get('tipo_pele')
        alergias = request.POST.get('alergias')
        descricao_alergia = request.POST.get('descricaoalergia')
        maquiagem = request.POST.get('maquiagem')
        pontos_sol = int(request.POST.get('reacao_sol', 0))
        base_produto = request.POST.get('base_produto')
        objective = request.POST.get('objetivo')

        quer_escanear = request.POST.get('quer_escanear') == 'sim'
        usa_maquiagem = 'sim' if maquiagem == '1' else 'nao'
        dados_ia_json = None
        foto_salva = None

        # calcula o score so com as respostas do questionario. esse e o valor padrao, usado sempre que a pessoa nao escaneia ou a API falha
        porcentagem_regras = calcular_porcentagem_saude(
            tipo_pele=tipo_pele,
            fototipo=pontos_sol + 1,
            usa_maquiagem=usa_maquiagem,
            tem_alergia=alergias,
        )
        porcentagem_calculada = porcentagem_regras

        if quer_escanear:
            foto_usuario = request.FILES.get('foto_rosto')

            if foto_usuario:
                resultados_ia = comunicar_youcam_api(foto_usuario)

                if resultados_ia:
                    dados_ia_json = json.dumps(resultados_ia)
                    foto_salva = resultados_ia.get('overlay_image_url') or resultados_ia.get('result_image_url')

                    try:
                        acne_score = resultados_ia.get('acne', {}).get('score', 80)
                        pore_score = resultados_ia.get('pore', {}).get('score', 80)
                        oil_score = resultados_ia.get('oiliness', {}).get('score', 80)
                        porcentagem_ia = int((acne_score + pore_score + oil_score) / 3)

                        # mistura o resultado da IA com o das regras, pra nao depender 100% de uma unica foto
                        porcentagem_calculada = round((porcentagem_ia + porcentagem_regras) / 2)
                    except Exception:
                        porcentagem_calculada = porcentagem_regras

        # 2. Salva ou atualiza as informações no banco de dados
        if request.user.is_authenticated:
            perfil, created = PerfilDermatologico.objects.get_or_create(
                usuario=request.user,
                defaults={
                    'idade': int(idade) if idade else 0,
                    'tipo_pele': tipo_pele or 'normal',
                    'alergias': alergias or '',
                    'objetivo': objective or 'Melhorar a pele',
                    'preferencia_produto': base_produto if base_produto in ('creme', 'gel') else 'gel',
                    'usa_maquiagem_diariamente': usa_maquiagem,
                    'porcentagem_saude': porcentagem_calculada,
                    'fototipo': pontos_sol + 1,
                    'dados_ia': dados_ia_json,
                    'foto_rosto': foto_salva,
                }
            )

            perfil.idade = int(idade) if idade else perfil.idade
            perfil.tipo_pele = tipo_pele or perfil.tipo_pele
            perfil.alergias = alergias or perfil.alergias
            perfil.usa_maquiagem_diariamente = usa_maquiagem
            perfil.fototipo = pontos_sol + 1
            perfil.objetivo = objective or perfil.objetivo
            perfil.preferencia_produto = base_produto if base_produto in ('creme', 'gel') else perfil.preferencia_produto
            perfil.porcentagem_saude = porcentagem_calculada
            perfil.dados_ia = dados_ia_json
            perfil.foto_rosto = foto_salva

            perfil.save()

        return redirect('dashboard')

    return render(request, 'core/questionario.html')

def dashboard_view(request):
    if request.user.is_authenticated:
        perfil = PerfilDermatologico.objects.filter(usuario=request.user).first()
    else:
        perfil = PerfilDermatologico.objects.first()
        
    rotina_manha = []
    rotina_noite = []
    if perfil:
        rotina_manha = [
            {
                'class': 'completed',
                'title': 'Limpeza Suave',
                'description': f'Rotina de limpeza diária para pele {perfil.tipo_pele}',
                'time': '08:00',
                'action': None,
                'icon': 'fa-check',
            },
            {
                'class': 'action-required' if perfil.porcentagem_saude < 80 else 'completed',
                'title': 'Hidratação & Tratamento',
                'description': f'Sérum recomendado para objetivo "{perfil.objetivo}"',
                'time': None if perfil.porcentagem_saude < 80 else '19:00',
                'action': 'Fazer agora' if perfil.porcentagem_saude < 80 else None,
                'icon': 'fa-check' if perfil.porcentagem_saude >= 80 else None,
            },
            {
                'class': 'pending' if perfil.fototipo and perfil.fototipo < 5 else 'completed',
                'title': 'Proteção Solar',
                'description': f'FPS 50+ para fototipo {perfil.fototipo or "1"}',
                'time': '12:00' if perfil.fototipo and perfil.fototipo < 5 else 'Já feito',
                'action': None,
                'icon': 'fa-check' if perfil.fototipo and perfil.fototipo >= 5 else None,
            },
        ]
        rotina_noite = [
            {
                'class': 'completed',
                'title': 'Remoção de Maquiagem',
                'description': 'Demaquilante suave antes de dormir',
                'time': '21:00',
                'action': None,
                'icon': 'fa-check',
            },
            {
                'class': 'completed',
                'title': 'Tratamento Noturno',
                'description': f'Sérum calmante para {perfil.tipo_pele}',
                'time': '21:30',
                'action': None,
                'icon': 'fa-check',
            },
            {
                'class': 'pending',
                'title': 'Hidratação Profunda',
                'description': 'Creme nutritivo para reparar enquanto dorme',
                'time': '22:00',
                'action': 'Aplicar agora',
                'icon': None,
            },
        ]

    context = {
        'perfil': perfil,
        'rotina_manha': rotina_manha,
        'rotina_noite': rotina_noite,
    }
    return render(request, 'core/dashboard.html', context)


def tela_login(request):
    if request.method == "POST":
        email = request.POST.get('email')
        senha = request.POST.get('senha')
        usuario = authenticate(request, username=email, password=senha)
        
        if usuario is not None:
            auth_login(request, usuario)
            return redirect('dashboard')
        else:
            return render(request, 'core/cadastro.html', {'erro': 'Usuário ou senha incorretos'})
            
    return render(request, 'core/login.html')

def tela_scanner(request):
    return render(request, 'core/scanner.html')

def tela_perfil(request):
    if request.user.is_authenticated:
        perfil = PerfilDermatologico.objects.filter(usuario=request.user).first()
    else:
        perfil = None

    context = {
        'perfil': perfil,
    }
    return render(request, 'core/perfil.html', context)

def tela_especialistas(request):
    return render(request, 'core/especialistas.html')

def tela_produtos(request):
    produtos_ficticios = [
        {
            "nome_produto": "Gel de Limpeza Facial",
            "descricao_produto": "Limpeza suave para pele mista",
            "url_foto_produto": "https://www.mockupworld.co/wp-content/uploads/dynamic/2023/02/standing-cosmetic-tube-free-mockup-psd-870x0-c-default.jpg",
            "categoria_produto": "limpeza",
        },
        {
            "nome_produto": "Sérum Hidratante",
            "descricao_produto": "Hidratação intensa com ácido hialurônico",
            "url_foto_produto": "https://www.mockupworld.co/wp-content/uploads/dynamic/2023/06/dropper-bottle-rubber-free-mockup-psd-870x0-c-default.jpg",
            "categoria_produto": "tratamento",
        },
        {
            "nome_produto": "Protetor Solar FPS 50",
            "descricao_produto": "Proteção UVA/UVB para uso diário",
            "url_foto_produto": "https://images.pexels.com/photos/19049367/pexels-photo-19049367.png",
            "categoria_produto": "protecao",
        },
        {
            "nome_produto": "Tônico Facial",
            "descricao_produto": "Equilibra o pH da pele após a limpeza",
            "url_foto_produto": "https://images.pexels.com/photos/6800931/pexels-photo-6800931.jpeg",
            "categoria_produto": "limpeza",
        },
        {
                    "nome_produto": "Esfoliante Facial",
                    "descricao_produto": "Remove células mortas da pele",
                    "url_foto_produto": "https://images.pexels.com/photos/8015480/pexels-photo-8015480.jpeg",
                    "categoria_produto": "limpeza",
                },
        {
                    "nome_produto": "Sabonete Facial Purificante",
                    "descricao_produto": "Controla oleosidade e brilho excessivo",
                    "url_foto_produto": "https://images.pexels.com/photos/8217468/pexels-photo-8217468.jpeg",
                    "categoria_produto": "limpeza",
                },
        {
                    "nome_produto": "Óleo de Limpeza Facial",
                    "descricao_produto": "Dissolve impurezas e protetor solar",
                    "url_foto_produto": "https://www.mockupworld.co/wp-content/uploads/dynamic/2023/02/dropper-bottle-medicine-free-mockup-psd-870x0-c-default.jpg",
                    "categoria_produto": "limpeza",
                },
     {
                    "nome_produto": "Espuma de Limpeza Suave",
                    "descricao_produto": "Limpa sem ressecar a pele sensível",
                    "url_foto_produto": "https://images.pexels.com/photos/7691163/pexels-photo-7691163.jpeg",
                    "categoria_produto": "limpeza",
             },
    ]

    filtro = request.GET.get("categoria")

    if filtro:
        produtos_filtrados = [p for p in produtos_ficticios if p["categoria_produto"] == filtro]
    else:
        produtos_filtrados = produtos_ficticios

    # Busca o perfil do usuário logado (relação OneToOne definida no model)
    perfil = PerfilDermatologico.objects.filter(usuario=request.user).first()

    context = {
        "perfil": perfil,
        "objetivo_usuario": perfil.objetivo if perfil else "não definido",
        "produtos": produtos_filtrados,
        "filtro_ativo": filtro,
    }
    return render(request, "core/produtos.html", context)

from django.shortcuts import render
from .models import Artigo

def tela_artigos(request):
    # TODO: trocar por Artigo.objects.all() quando a tabela existir de fato
    artigos_ficticios = [
        {
            "titulo": "A importância do cuidado diário na saúde da pele",
            "autor": "Lima, J. C. et al.",
            "ano": 2023,
            "url_capa": "https://placehold.co/120x160?text=Artigo",
            "url_leitura": "https://rsdjournal.org/index.php/rsd/article/view/41571",
        },
        {
            "titulo": "A importância da hidratação cutânea para melhor tratamento das disfunções estéticas",
            "autor": "AMARAL, K. F. V.; SOUZA, R. B. A. A",
            "ano": 2018,
            "url_capa": "https://placehold.co/120x160?text=Artigo",
            "url_leitura": "https://idonline.emnuvens.com.br/id/article/view/2284",
        },
        {
            "titulo": "Dermatologia na Atenção Básica de Saúde",
            "autor": "Ministério da Saúde do Brasil",
            "ano": 2002,
            "url_capa": "https://placehold.co/120x160?text=Artigo",
            "url_leitura": "https://saude.gov.br/",
        },
        {
            "titulo": "Artigo Científico",
            "autor": "Autor(a)",
            "ano": 2000,
            "url_capa": "https://placehold.co/120x160?text=Artigo",
            "url_leitura": "#",
        }
    ]
    context = {
        "artigos": artigos_ficticios,
    }
    return render(request, "core/artigos.html", context)

from django.shortcuts import render

def tela_especialistas(request):
    especialistas_ficticios = [
        {
            "nome": "Dra. Ana Beatriz",
            "especialidade": "dermatologista",
            "crm": "CRM 45213-RS",
            "telefone_whatsapp": "5551999990001",
        },
        {
            "nome": "Dr. Rafael Silva",
            "especialidade": "dermatologista",
            "crm": "CRM 38712-RS",
            "telefone_whatsapp": "5551999990002",
        },
        {
            "nome": "Dra.Camila Rodrigues",
            "especialidade": "esteticista",
            "crm": "CRM 51234-RS",
            "telefone_whatsapp": "5551999990003",
        },
        {
            "nome": "Dra. Luísa Souza",
            "especialidade": "cosmetologo",
            "crm": "CRM 51890-RS",
            "telefone_whatsapp": "5551999990004",
        },
    ]

    filtro = request.GET.get("especialidade")

    if filtro:
        especialistas_filtrados = [e for e in especialistas_ficticios if e["especialidade"] == filtro]
    else:
        especialistas_filtrados = especialistas_ficticios

    context = {
        "especialistas": especialistas_filtrados,
        "filtro_ativo": filtro,
    }
    return render(request, "core/especialistas.html", context)