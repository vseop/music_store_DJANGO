from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import *


class MembersInline(admin.TabularInline):
    model = Artist.members.through

class ImageGalleryInline(GenericTabularInline):

    model = ImageGallery
    readonly_fields = ('image_url',)

    def image_url(self, obj):
        return mark_safe(f'<img src="{obj.image.url}" width="auto" height="200px"')

    image_url.short_description = "Изображение"

@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):

    inlines = [ImageGalleryInline]

@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):

    inlines = [MembersInline, ImageGalleryInline]
    exclude = ('members',)



admin.site.register(Genre)
admin.site.register(Member)
admin.site.register(MediaType)
admin.site.register(ImageGallery)
admin.site.register(Cart)
admin.site.register(CartProduct)
admin.site.register(Order)
admin.site.register(Customer)
admin.site.register(Notification)

admin.site.site_title = "Административная панель"
admin.site.site_header = "Административная панель"