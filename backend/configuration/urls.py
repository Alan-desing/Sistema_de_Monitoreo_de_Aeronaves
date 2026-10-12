from django.urls import path

from . import views

urlpatterns = [
    path("config/", views.ConfigView.as_view()),
    path("config/openair/", views.OpenAirView.as_view()),
    path("config/telegram-test/", views.TelegramTestView.as_view()),
]
