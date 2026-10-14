from django.urls import path
from django.contrib import admin
from portal import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [path('admin/', admin.site.urls), path('', views.home, name='home'), path('registros/', views.records, name='records'), path('atendimentos/novo/', views.register, name='register')]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
