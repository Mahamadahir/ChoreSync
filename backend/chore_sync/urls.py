"""
URL configuration for chore_sync project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from chore_sync.api.views import (
    SignupAPIView,
    LoginAPIView,
    ResendVerificationAPIView,
    VerifyEmailAPIView,
    LogoutAPIView,
    UpdateEmailAPIView,
    ProfileAPIView,
    ForgotPasswordAPIView,
    ResetPasswordAPIView,
    ChangePasswordAPIView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/signup/', SignupAPIView.as_view(), name='signup'),
    path('api/auth/login/', LoginAPIView.as_view(), name='login'),
    path('api/auth/resend-verification/', ResendVerificationAPIView.as_view(), name='resend-verification'),
    path('api/auth/verify-email/', VerifyEmailAPIView.as_view(), name='verify-email'),
    path('api/auth/update-email/', UpdateEmailAPIView.as_view(), name='update-email'),
    path('api/auth/logout/', LogoutAPIView.as_view(), name='logout'),
    path('api/auth/forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot-password'),
    path('api/auth/reset-password/', ResetPasswordAPIView.as_view(), name='reset-password'),
    path('api/auth/change-password/', ChangePasswordAPIView.as_view(), name='change-password'),
    path('api/profile/', ProfileAPIView.as_view(), name='profile'),
    # TODO: add group/task endpoints via DRF views or viewsets
]
