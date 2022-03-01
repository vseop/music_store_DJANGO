import operator
from calendar import monthrange
from datetime import datetime

from django.conf import settings

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models, connection
from django.db.models.signals import post_save, pre_save
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from utils import upload_function


class MediaType(models.Model):
    """Медианоситель"""

    name = models.CharField(max_length=100, verbose_name='Название медианосителя')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Медианоситель'
        verbose_name_plural = 'Медианосители'


class Member(models.Model):
    """Музыкант"""

    name = models.CharField(max_length=255, verbose_name='Имя музыканта')
    slug = models.SlugField()
    image = models.ImageField(upload_to=upload_function, null=True, blank=True, verbose_name='Постер')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Музыкант'
        verbose_name_plural = 'Музыканты'


class Genre(models.Model):
    """Музыкальный жанр"""

    name = models.CharField(max_length=50, verbose_name='Название жанра')
    slug = models.SlugField()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Жанр'
        verbose_name_plural = 'Жанры'


class Artist(models.Model):
    """Исполнитель"""

    name = models.CharField(max_length=255, verbose_name='Исполнитель/группа')
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE, verbose_name='Жанр')
    members = models.ManyToManyField(Member, verbose_name='Участник', related_name='artist')
    image_gallery = GenericRelation('imagegallery')
    slug = models.SlugField()
    image = models.ImageField(upload_to=upload_function, null=True, blank=True, verbose_name='Постер')

    def __str__(self):
        return f'{self.name} | {self.genre.name}'

    def get_absolute_url(self):
        return reverse('artist_detail', kwargs={'artist_slug': self.slug})

    class Meta:
        verbose_name = 'Исполнитель'
        verbose_name_plural = 'Исполнители'


class AlbumManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset()

    def get_month_bestseller(self):
        today = datetime.today()
        year, month = today.year, today.month
        first_day = datetime(year, month, 1)
        last_day = datetime(year, month, monthrange(year, month)[1])
        query = f"""
            SELECT shop_product.id as product_id, SUM(distinct shop_cart_product.qty) as total_qty
            FROM mainapp_order as shop_order
            JOIN mainapp_cart as shop_cart on shop_order.cart_id = shop_cart.id
            JOIN mainapp_cartproduct as shop_cart_product on shop_cart.id = shop_cart_product.cart_id
            JOIN mainapp_album as shop_product on shop_cart_product.object_id=shop_product.id
            WHERE shop_order.order_date >= '{first_day}' and shop_order.order_date <= '{last_day}'
            GROUP BY product_id
            ORDER BY total_qty DESC
            LIMIT 1
        """
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()
        if row:
            product_id, qty = row
            album = Album.objects.get(pk=product_id)
            return album, qty
        return None, None


class Album(models.Model):
    """Альбом исполнителя"""

    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, verbose_name='Исполнитель')
    name = models.CharField(max_length=255, verbose_name='Название альбома')
    media_type = models.ForeignKey(MediaType, verbose_name='Носитель', on_delete=models.CASCADE)
    song_list = models.TextField(verbose_name='Трэклист')
    release_date = models.DateField(verbose_name='Дата релиза')
    slug = models.SlugField()
    description = models.TextField(verbose_name='Описание', default='Описание появится позже')
    stock = models.IntegerField(default=1, verbose_name='Наличие на складе')
    out_of_stock = models.BooleanField(default=False, verbose_name='Нет в наличии')
    price = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Цена')
    offer_of_the_week = models.BooleanField(default=False, verbose_name='Предложение недели?')
    image = models.ImageField(upload_to=upload_function, verbose_name='Постер')
    objects = AlbumManager()

    def __str__(self):
        return f'{self.id} | {self.artist.name} | {self.name}'

    @property
    def ct_model(self):
        return self._meta.model_name

    def get_absolute_url(self):
        return reverse('album_detail', kwargs={'artist_slug': self.artist.slug, 'album_slug': self.slug})

    class Meta:
        verbose_name = 'Альбом'
        verbose_name_plural = 'Альбомы'


class CartProduct(models.Model):
    """Продукт корзины"""

    MODEL_CARTPRODUCT_DISPLAY_NAME_MAP = {
        "Album": {"is_constructable": True, "fields": ["name", "artist.name"], "separator": ' - '}
    }

    user = models.ForeignKey('Customer', verbose_name='Покупатель', on_delete=models.CASCADE)
    cart = models.ForeignKey('Cart', verbose_name='Корзина', on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    qty = models.PositiveIntegerField(default=1, verbose_name='Количество')
    final_price = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Общая цена')

    def __str__(self):
        return f'Продукт: {self.content_object.name} (для корзины)'

    @property
    def display_name(self):
        """Конструктор имени продукта для корзины по заданным полям,
        необходим при увеличении ассортимента продоваемой продукции (музыкальные инструменты, проигрователи ...) """

        model_fields = self.MODEL_CARTPRODUCT_DISPLAY_NAME_MAP.get(self.content_object.__class__._meta.model_name.capitalize())
        if model_fields and model_fields['is_constructable']:
            display_name = model_fields['separator'].join(
                [operator.attrgetter(field)(self.content_object) for field in model_fields['fields']]
            )
            return display_name
        if model_fields and not model_fields['is_constructable']:
            display_name = operator.attrgetter(model_fields['field'])(self.content_object)
            return display_name

        return self.content_object

    def save(self, *args, **kwargs):
        self.final_price = self.qty * self.content_object.price
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Продукт корзины'
        verbose_name_plural = 'Продукты корзины'


class Cart(models.Model):
    """Корзина"""

    owner = models.ForeignKey('Customer', verbose_name='Покупатель', on_delete=models.CASCADE)
    products = models.ManyToManyField(
        CartProduct, blank=True, related_name='related_cart', verbose_name='Продукты для корзины')
    total_products = models.IntegerField(default=0, verbose_name='Общее кол-во товара')
    final_price = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Общая цена', null=True, blank=True)
    in_order = models.BooleanField(default=False)
    for_anonymous_user = models.BooleanField(default=False)

    def __str__(self):
        return str(self.id)

    def products_in_cart(self):
        return [c.content_object for c in self.products.all()]

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'


class Order(models.Model):
    """Заказ пользователя"""

    STATUS_NEW = 'new'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_READY = 'is_ready'
    STATUS_COMPLETED = 'completed'

    BUYING_TYPE_SELF = 'self'
    BUYING_TYPE_DELIVERY = 'delivery'

    STATUS_CHOICES = (
        (STATUS_NEW, 'Новый заказ'),
        (STATUS_IN_PROGRESS, 'Заказ в обработке'),
        (STATUS_READY, 'Заказ готов'),
        (STATUS_COMPLETED, 'Заказ получен покупателем')
    )

    BUYING_TYPE_CHOICES = (
        (BUYING_TYPE_SELF, 'Самовывоз'),
        (BUYING_TYPE_DELIVERY, 'Доставка')
    )

    customer = models.ForeignKey(
        'Customer', verbose_name='Покупатель', related_name='orders', on_delete=models.CASCADE)
    first_name = models.CharField(max_length=255, verbose_name='Имя')
    last_name = models.CharField(max_length=255, verbose_name='Фамилия')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    cart = models.ForeignKey(Cart, verbose_name='Корзина', null=True, blank=True, on_delete=models.CASCADE)
    address = models.CharField(max_length=255, verbose_name='Адрес', null=True, blank=True)
    status = models.CharField(
        max_length=100, verbose_name='Статус заказа', choices=STATUS_CHOICES, default=STATUS_NEW)
    buying_type = models.CharField(max_length=100, verbose_name='Тип заказа', choices=BUYING_TYPE_CHOICES)
    comment = models.TextField(verbose_name='Комментарий к заказу', null=True, blank=True)
    created_at = models.DateField(verbose_name='Дата создания заказа', auto_now=True)
    order_date = models.DateField(verbose_name='Дата получения заказа', default=timezone.now)

    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'


class Customer(models.Model):
    """Покупатель"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='Пользователь', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True, verbose_name='Активный?')
    customer_orders = models.ManyToManyField(
        Order, blank=True, verbose_name='Заказы покупателя', related_name='related_customer')
    wishlist = models.ManyToManyField(Album, verbose_name='Лист ожидания', blank=True)
    phone = models.CharField(max_length=20, verbose_name='Номер телефона для связи')
    address = models.TextField(null=True, verbose_name='Адрес доставки', blank=True)

    def __str__(self):
        return f'{self.user.username}'

    class Meta:
        verbose_name = 'Покупатель'
        verbose_name_plural = 'Покупатели'


class NotificationManager(models.Manager):
    """Менеджер уведомлений"""

    def get_queryset(self):
        return super().get_queryset()

    def all(self, recipient):
        return self.get_queryset().filter(
            recipient=recipient,
            read=False
        )

    def make_all_read(self, recipient):
        qs = self.get_queryset().filter(recipient=recipient, read=False)
        qs.update(read=True)


class Notification(models.Model):
    """Уведомления"""

    recipient = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name='Получатель')
    text = models.TextField(verbose_name='Текст сообщения')
    read = models.BooleanField(default=False, verbose_name='Прочтено?')
    objects = NotificationManager()

    def __str__(self):
        return f'Уведомление для {self.recipient.user.username} | id={self.id}'

    class Meta:
        verbose_name = 'Уведомления'
        verbose_name_plural = 'Уведомления'


class ImageGallery(models.Model):
    """Галерея изображений"""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    image = models.ImageField(upload_to=upload_function)
    use_in_slider = models.BooleanField(default=False)

    def __str__(self):
        return f'Изображение для {self.content_object}'

    # def image_url(self):
    #     return mark_safe(f'<img src="{self.image.url}" width="auto" height="200px"')

    class Meta:
        verbose_name = 'Галерея изображений'
        verbose_name_plural = verbose_name


def check_previous_qty(instance, **kwargs):
    try:
        album = Album.objects.get(id=instance.id)
    except Album.DoesNotExist:
        return None
    instance.out_of_stock = True if not album.stock else False


def send_notification(instance, **kwargs):
    if instance.stock and instance.out_of_stock:
        customers = Customer.objects.filter(
            wishlist__in=[instance]
        )
        if customers.count():
            for c in customers:
                Notification.objects.create(
                    recipient=c,
                    text=mark_safe(f'Позиция <a href="{instance.get_absolute_url()}">{instance.name}</a>, '
                                   f'которую Вы ожидаете, есть в наличии.')
                )
                c.wishlist.remove(instance)


post_save.connect(send_notification, sender=Album)
pre_save.connect(check_previous_qty, sender=Album)
