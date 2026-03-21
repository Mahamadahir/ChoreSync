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

from chore_sync.api.task_template_router import (
    GroupTaskTemplateListCreateAPIView,
    TaskTemplateDetailAPIView,
)
from chore_sync.api.task_router import (
    UserTaskListAPIView,
    GroupTaskListAPIView,
    GenerateOccurrencesAPIView,
    TaskOccurrenceDetailAPIView,
    TaskCompleteAPIView,
    TaskSnoozeAPIView,
    TaskSwapCreateAPIView,
    TaskSwapRespondAPIView,
    TaskEmergencyReassignAPIView,
    TaskAcceptEmergencyAPIView,
)
from chore_sync.api.group_router import (
    GroupListCreateAPIView,
    GroupDetailAPIView,
    GroupInviteAPIView,
    GroupMembersAPIView,
    GroupAssignmentMatrixAPIView,
    GroupSettingsAPIView,
)
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
    GoogleLoginAPIView,
    MicrosoftLoginAPIView,
    EventsAPIView,
    EventDetailAPIView,
    GoogleCalendarAuthURLAPIView,
    GoogleCalendarCallbackAPIView,
    GoogleCalendarSyncAPIView,
    GoogleCalendarListAPIView,
    GoogleCalendarSelectAPIView,
    GoogleCalendarWebhookAPIView,
    EventStreamAPIView,
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
    path('api/auth/google/', GoogleLoginAPIView.as_view(), name='google-login'),
    path('api/auth/microsoft/', MicrosoftLoginAPIView.as_view(), name='microsoft-login'),
    path('api/profile/', ProfileAPIView.as_view(), name='profile'),
    path('api/events/', EventsAPIView.as_view(), name='events'),
    path('api/events/<int:pk>/', EventDetailAPIView.as_view(), name='event-detail'),
    path('api/calendar/google/list/', GoogleCalendarListAPIView.as_view(), name='google-cal-list'),
    path('api/calendar/google/select/', GoogleCalendarSelectAPIView.as_view(), name='google-cal-select'),
    path('api/calendar/google/auth-url/', GoogleCalendarAuthURLAPIView.as_view(), name='google-cal-auth-url'),
    path('api/calendar/google/callback/', GoogleCalendarCallbackAPIView.as_view(), name='google-cal-callback'),
    path('api/calendar/google/sync/', GoogleCalendarSyncAPIView.as_view(), name='google-cal-sync'),
    path('api/calendar/google/webhook/', GoogleCalendarWebhookAPIView.as_view(), name='google-cal-webhook'),
    path('api/events/stream/', EventStreamAPIView.as_view(), name='event-stream'),
    path('api/groups/', GroupListCreateAPIView.as_view(), name='group-list-create'),
    path('api/groups/<uuid:pk>/', GroupDetailAPIView.as_view(), name='group-detail'),
    path('api/groups/<uuid:pk>/invite/', GroupInviteAPIView.as_view(), name='group-invite'),
    path('api/groups/<uuid:pk>/members/', GroupMembersAPIView.as_view(), name='group-members'),
    path('api/groups/<uuid:pk>/assignment-matrix/', GroupAssignmentMatrixAPIView.as_view(), name='group-assignment-matrix'),
    path('api/groups/<uuid:pk>/settings/', GroupSettingsAPIView.as_view(), name='group-settings'),
    path('api/groups/<uuid:pk>/task-templates/', GroupTaskTemplateListCreateAPIView.as_view(), name='group-task-templates'),
    path('api/task-templates/<int:pk>/', TaskTemplateDetailAPIView.as_view(), name='task-template-detail'),
    path('api/task-templates/<int:pk>/generate-occurrences/', GenerateOccurrencesAPIView.as_view(), name='task-template-generate-occurrences'),
    path('api/users/me/tasks/', UserTaskListAPIView.as_view(), name='user-tasks'),
    path('api/groups/<uuid:pk>/tasks/', GroupTaskListAPIView.as_view(), name='group-tasks'),
    path('api/tasks/<int:pk>/', TaskOccurrenceDetailAPIView.as_view(), name='task-detail'),
    path('api/tasks/<int:pk>/complete/', TaskCompleteAPIView.as_view(), name='task-complete'),
    path('api/tasks/<int:pk>/snooze/', TaskSnoozeAPIView.as_view(), name='task-snooze'),
    path('api/tasks/<int:pk>/swap/', TaskSwapCreateAPIView.as_view(), name='task-swap-create'),
    path('api/task-swaps/<int:pk>/respond/', TaskSwapRespondAPIView.as_view(), name='task-swap-respond'),
    path('api/tasks/<int:pk>/emergency-reassign/', TaskEmergencyReassignAPIView.as_view(), name='task-emergency-reassign'),
    path('api/tasks/<int:pk>/accept-emergency/', TaskAcceptEmergencyAPIView.as_view(), name='task-accept-emergency'),
]
