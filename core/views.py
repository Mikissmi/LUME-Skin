from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, authenticate, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from .models import Usuario, PerfilDermatologico, Artigo, Especialista
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


def tela_logout(request):
    if request.method == "POST":
        auth_logout(request)
    return redirect('login')


# ==========================================================================
# SCANNER DE PELE POR IA - endpoints usados pelo JS da core/scanner.html
# ==========================================================================

def classificar_indicador(nota):
    if nota >= 85:
        return 'Ótimo'
    if nota >= 70:
        return 'Bom'
    if nota >= 50:
        return 'Regular'
    return 'Atenção'


DESCRICOES_INDICADOR = {
    'oleosidade': {
        'Ótimo': 'Oleosidade sob controle.',
        'Bom': 'Nível de oleosidade equilibrado.',
        'Regular': 'Zona T pode precisar de atenção.',
        'Atenção': 'Oleosidade elevada, considere um produto de controle.',
    },
    'hidratacao': {
        'Ótimo': 'Hidratação excelente.',
        'Bom': 'Nível de hidratação adequado.',
        'Regular': 'Pele levemente desidratada.',
        'Atenção': 'Baixa hidratação, reforce o uso de hidratante.',
    },
    'acne_poros': {
        'Ótimo': 'Poucos sinais de acne ou poros dilatados.',
        'Bom': 'Poros e acne sob controle.',
        'Regular': 'Alguns poros dilatados e pequenas inflamações.',
        'Atenção': 'Sinais de acne e poros dilatados precisam de cuidado.',
    },
    'textura': {
        'Ótimo': 'Textura uniforme e lisa.',
        'Bom': 'Boa textura geral da pele.',
        'Regular': 'Leve irregularidade na textura.',
        'Atenção': 'Textura irregular, considere uma esfoliação leve.',
    },
    'manchas': {
        'Ótimo': 'Tonalidade bem uniforme.',
        'Bom': 'Poucas manchas visíveis.',
        'Regular': 'Algumas manchas de sol ou idade.',
        'Atenção': 'Manchas visíveis, reforce o uso de protetor solar.',
    },
}


def montar_indicador(chave, nota):
    nota = max(0, min(100, round(nota)))
    classificacao = classificar_indicador(nota)
    descricao = DESCRICOES_INDICADOR[chave][classificacao]
    return {'chave': chave, 'nota': nota, 'classificacao': classificacao, 'descricao': descricao}


def scanner_analisar(request):
    # recebe a foto tirada/enviada na tela do scanner e devolve a analise em json
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido.'}, status=405)

    foto = request.FILES.get('foto')
    if not foto:
        return JsonResponse({'erro': 'Nenhuma imagem enviada.'}, status=400)

    resultados_ia = comunicar_youcam_api(foto)
    if not resultados_ia:
        return JsonResponse({'erro': 'Não foi possível analisar a imagem agora. Tente novamente em instantes.'}, status=502)

    nota_oleosidade = resultados_ia.get('oiliness', {}).get('score', 70)
    nota_hidratacao = resultados_ia.get('moisture', {}).get('score', 70)
    nota_acne = resultados_ia.get('acne', {}).get('score', 70)
    nota_poros = resultados_ia.get('pore', {}).get('score', 70)
    nota_textura = resultados_ia.get('texture', {}).get('score', 70)
    nota_manchas = resultados_ia.get('age_spot', {}).get('score', 70)

    indicadores = [
        montar_indicador('oleosidade', nota_oleosidade),
        montar_indicador('hidratacao', nota_hidratacao),
        montar_indicador('acne_poros', (nota_acne + nota_poros) / 2),
        montar_indicador('textura', nota_textura),
        montar_indicador('manchas', nota_manchas),
    ]

    score_geral = round(sum(indicador['nota'] for indicador in indicadores) / len(indicadores))
    mapeamento_facial = resultados_ia.get('overlay_image_url') or resultados_ia.get('result_image_url')

    # guarda o resultado na sessão pra "Salvar Check-in" nao precisar reenviar a foto/analise inteira
    request.session['ultimo_scan'] = {
        'dados_ia': json.dumps(resultados_ia),
        'foto_rosto': mapeamento_facial,
        'porcentagem_saude': score_geral,
    }

    return JsonResponse({
        'score_geral': score_geral,
        'indicadores': indicadores,
        'mapeamento_facial': mapeamento_facial,
    })


def scanner_salvar(request):
    # salva o ultimo resultado de scanner (guardado na sessao) no perfil dermatologico do usuario
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido.'}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({'erro': 'Você precisa estar logado para salvar o check-in.'}, status=401)

    ultimo_scan = request.session.get('ultimo_scan')
    if not ultimo_scan:
        return JsonResponse({'erro': 'Faça um scan antes de salvar o check-in.'}, status=400)

    perfil, _ = PerfilDermatologico.objects.get_or_create(
        usuario=request.user,
        defaults={
            'idade': 0,
            'tipo_pele': 'normal',
            'objetivo': 'Melhorar a pele',
            'preferencia_produto': 'gel',
            'usa_maquiagem_diariamente': 'nao',
            'porcentagem_saude': ultimo_scan['porcentagem_saude'],
        },
    )

    perfil.dados_ia = ultimo_scan['dados_ia']
    perfil.foto_rosto = ultimo_scan['foto_rosto']
    perfil.porcentagem_saude = ultimo_scan['porcentagem_saude']
    perfil.save()

    del request.session['ultimo_scan']
    return JsonResponse({'ok': True})


def tela_scanner(request):
    return render(request, 'core/scanner.html')


# ==========================================================================
# PERFIL DO USUÁRIO
# ==========================================================================

def tela_perfil(request):
    if request.user.is_authenticated:
        perfil = PerfilDermatologico.objects.filter(usuario=request.user).first()
    else:
        perfil = None

    context = {
        'perfil': perfil,
    }
    return render(request, 'core/perfil.html', context)


@login_required
def editar_perfil(request):
    # o formulario de edicao fica embutido direto na aba "Preferencias da Conta"
    # de core/perfil.html, entao essa view so processa o POST e volta pra la
    perfil = PerfilDermatologico.objects.filter(usuario=request.user).first()
    if not perfil:
        return redirect('questionario')

    destino = f"{reverse('perfil')}?aba=conta"

    if request.method != 'POST':
        return redirect(destino)

    nome_usuario = request.POST.get('nome_usuario', '').strip()
    idade = request.POST.get('idade')
    tipo_pele = request.POST.get('tipo_pele')
    alergias = request.POST.get('alergias', '').strip()
    objetivo = request.POST.get('objetivo', '').strip()
    preferencia_produto = request.POST.get('preferencia_produto')
    usa_maquiagem_diariamente = request.POST.get('usa_maquiagem_diariamente')

    if nome_usuario:
        request.user.nome_usuario = nome_usuario
        request.user.save()

    if idade:
        perfil.idade = int(idade)
    if tipo_pele in dict(PerfilDermatologico.TIPO_PELE_CHOICES):
        perfil.tipo_pele = tipo_pele
    perfil.alergias = alergias
    if objetivo:
        perfil.objetivo = objetivo
    if preferencia_produto in ('creme', 'gel'):
        perfil.preferencia_produto = preferencia_produto
    if usa_maquiagem_diariamente in ('sim', 'nao'):
        perfil.usa_maquiagem_diariamente = usa_maquiagem_diariamente

    perfil.save()
    return redirect(destino)


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


def tela_artigos(request):
    artigos = Artigo.objects.all().order_by('-ano')
    context = {
        "artigos": artigos,
    }
    return render(request, "core/artigos.html", context)


def tela_especialistas(request):
    especialistas = Especialista.objects.all().order_by('nome')

    filtro = request.GET.get("especialidade")

    if filtro:
        especialistas = especialistas.filter(especialidade=filtro)

    context = {
        "especialistas": especialistas,
        "filtro_ativo": filtro,
    }
    return render(request, "core/especialistas.html", context)


# ==========================================================================
# ÁREA ADMINISTRATIVA - CRUD de artigos e especialistas
# ==========================================================================

@login_required
def tela_administradores(request):
    context = {
        "artigos": Artigo.objects.all().order_by('-ano'),
        "especialistas": Especialista.objects.all().order_by('nome'),
    }
    return render(request, "core/administradores.html", context)


@login_required
def artigo_form(request, artigo_id=None):
    # os formularios de criar/editar artigo ficam embutidos direto em
    # core/administradores.html, entao essa view so processa o POST
    if request.method != 'POST':
        return redirect('administradores')

    artigo = get_object_or_404(Artigo, id=artigo_id) if artigo_id else Artigo()

    artigo.titulo = request.POST.get('titulo', '').strip()
    artigo.autor = request.POST.get('autor', '').strip()
    artigo.ano = request.POST.get('ano') or artigo.ano
    artigo.resumo = request.POST.get('resumo', '').strip()
    artigo.url_capa = request.POST.get('url_capa', '').strip()
    artigo.url_leitura = request.POST.get('url_leitura', '').strip()
    artigo.save()
    return redirect('administradores')


@login_required
def artigo_excluir(request, artigo_id):
    artigo = get_object_or_404(Artigo, id=artigo_id)
    if request.method == 'POST':
        artigo.delete()
    return redirect('administradores')


@login_required
def especialista_form(request, especialista_id=None):
    # os formularios de criar/editar especialista ficam embutidos direto em
    # core/administradores.html, entao essa view so processa o POST
    if request.method != 'POST':
        return redirect('administradores')

    especialista = get_object_or_404(Especialista, id=especialista_id) if especialista_id else Especialista()

    especialista.nome = request.POST.get('nome', '').strip()
    especialista.especialidade = request.POST.get('especialidade', '').strip()
    especialista.crm = request.POST.get('crm', '').strip()
    especialista.telefone_whatsapp = request.POST.get('telefone_whatsapp', '').strip()
    especialista.url_foto = request.POST.get('url_foto', '').strip()
    especialista.save()
    return redirect('administradores')


@login_required
def especialista_excluir(request, especialista_id):
    especialista = get_object_or_404(Especialista, id=especialista_id)
    if request.method == 'POST':
        especialista.delete()
    return redirect('administradores')
