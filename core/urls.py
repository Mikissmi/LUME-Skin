from django.urls import path
from . import views

urlpatterns = [
    # Rota raiz do site direcionando para cadastro
    path('', views.tela_cadastro, name='home'),

    # Rota para a tela de cadastro (página inicial alternativa)
    path('cadastro/', views.tela_cadastro, name='cadastro_view'),
    
    # Rota para o questionário
    path('questionario/', views.tela_questionario, name='questionario'),
    
    # Rota para a página de login
    path('login/', views.tela_login, name='login'),

    # Rota para encerrar a sessão do usuário
    path('logout/', views.tela_logout, name='logout'),

    # Rota para o Dashboard (que criamos nos passos anteriores)
    # Certifique-se de que a função 'dashboard_view' exista no seu views.py
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Rota para a página do scanner
    path('scanner/', views.tela_scanner, name='scanner'),

    # Rotas do backend do scanner (chamadas via fetch/JS pela core/scanner.html)
    path('scanner/analisar/', views.scanner_analisar, name='scanner_analisar'),
    path('scanner/salvar/', views.scanner_salvar, name='scanner_salvar'),

    # Rota para a página do perfil do usuário
    path('perfil/', views.tela_perfil, name='perfil'),

    # Rota para editar as preferências do perfil do usuário
    path('perfil/editar/', views.editar_perfil, name='editar_perfil'),

    # Rota para a página dos especialistas
    path('especialistas/', views.tela_especialistas, name='especialistas'),

    # Rota para a página dos produtos recomendados
    path('produtos/', views.tela_produtos, name='produtos'),

    # Rota para a página dos artigos
    path('artigos/', views.tela_artigos, name='artigos'),

    # Rota para o painel administrativo (gerencia artigos e especialistas)
    path('administradores/', views.tela_administradores, name='administradores'),

    # CRUD de artigos usado pelo painel administrativo
    path('administradores/artigos/novo/', views.artigo_form, name='artigo_novo'),
    path('administradores/artigos/<int:artigo_id>/editar/', views.artigo_form, name='artigo_editar'),
    path('administradores/artigos/<int:artigo_id>/excluir/', views.artigo_excluir, name='artigo_excluir'),

    # CRUD de especialistas usado pelo painel administrativo
    path('administradores/especialistas/novo/', views.especialista_form, name='especialista_novo'),
    path('administradores/especialistas/<int:especialista_id>/editar/', views.especialista_form, name='especialista_editar'),
    path('administradores/especialistas/<int:especialista_id>/excluir/', views.especialista_excluir, name='especialista_excluir'),

]