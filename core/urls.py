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
    
    # Rota para o Dashboard (que criamos nos passos anteriores)
    # Certifique-se de que a função 'dashboard_view' exista no seu views.py
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Rota para a página do scanner
    path('scanner/', views.tela_scanner, name='scanner'),
    
    # Rota para a página do perfil do usuário
    path('perfil/', views.tela_perfil, name='perfil'),

    # Rota para a página dos especialistas
    path('especialistas/', views.tela_especialistas, name='especialistas'),
]