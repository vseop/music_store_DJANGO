from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from ajax_select import urls as ajax_select_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ajax_select/', include(ajax_select_urls)),
    path('', include('mainapp.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
