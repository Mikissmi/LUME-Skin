from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser


class UsuarioManager(BaseUserManager):
    # gerenciador customizado, porque nosso Usuario nao tem o campo "username" padrao do Django
    def create_user(self, email, nome_usuario, password=None):
        if not email:
            raise ValueError('É obrigatório informar um email')

        usuario = self.model(
            email=self.normalize_email(email),
            nome_usuario=nome_usuario,
        )
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario


class Usuario(AbstractBaseUser):
    # esse model substitui o User padrao do Django, pra bater com a tabela "usuario" do nosso banco
    id_usuario = models.AutoField(primary_key=True)
    nome_usuario = models.CharField(max_length=100)
    email = models.EmailField(max_length=200, unique=True)
    password = models.CharField(max_length=100, db_column='senha_usuario')
    data_cadastro = models.DateTimeField(auto_now_add=True)

    # tira o campo last_login que o AbstractBaseUser adiciona sozinho,
    # porque a tabela "usuario" do nosso banco nao tem essa coluna
    last_login = None

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome_usuario']

    objects = UsuarioManager()

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return self.email


class PerfilDermatologico(models.Model):
    # Conecta o perfil ao usuário criado no cadastro
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, db_column='id_usuario')

    # Dados do questionário
    idade = models.IntegerField()
    TIPO_PELE_CHOICES = [
        ('oleosa', 'Oleosa'),
        ('seca', 'Seca'),
        ('mista', 'Mista'),
        ('normal', 'Normal'),
    ]
    tipo_pele = models.CharField(max_length=10, choices=TIPO_PELE_CHOICES)
    alergias = models.TextField(blank=True, null=True)
    objetivo = models.CharField(max_length=200)
    preferencia_produto = models.CharField(max_length=10, choices=[('creme', 'Creme'), ('gel', 'Gel')])
    usa_maquiagem_diariamente = models.CharField(max_length=10)

    # Campos que ficam vazios por enquanto, sem o escaneamento por IA
    foto_rosto = models.CharField(max_length=500, blank=True, null=True)
    dados_ia = models.TextField(blank=True, null=True)

    # Dados calculados pelo sistema posteriormente
    porcentagem_saude = models.IntegerField()
    fototipo = models.IntegerField(blank=True, null=True)  # Escala de 1 a 6

    class Meta:
        db_table = 'perfil_dermatologico'
