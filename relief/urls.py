from django.urls import path
from . import views
app_name = "relief"
urlpatterns = [path("", views.home, name="home"), path("chat/", views.chat, name="chat"), path("find-help/", views.resource_finder, name="resource_finder")]
