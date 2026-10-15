from django.urls import path
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from portal import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', views.home, name='home'),
    path('registros/', views.records, name='records'),
    path('atendimentos/novo/', views.register, name='register'),
    path('atendimentos/<int:pk>/editar/', views.edit_atendimento, name='edit_atendimento'),
    path('atendimentos/<int:pk>/excluir/', views.delete_atendimento, name='delete_atendimento'),
    path('media/<path:path>', views.protected_media, name='protected_media'),
]
