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
from django.conf import settings
from django.conf.urls.static import static
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
    TaskPhotoProofAPIView,
    PendingSwapsAPIView,
    TaskAcceptSuggestionAPIView,
    TaskDeclineSuggestionAPIView,
    TaskOccurrenceAssignmentBreakdownAPIView,
)
from chore_sync.api.marketplace_router import (
    TaskListMarketplaceAPIView,
    GroupMarketplaceListAPIView,
    MarketplaceCancelAPIView,
    MarketplaceClaimAPIView,
)
from chore_sync.api.stats_router import (
    UserStatsAPIView,
    UserBadgesAPIView,
    GroupStatsAPIView,
)
from chore_sync.api.proposal_router import (
    GroupProposalListCreateAPIView,
    ProposalApproveAPIView,
    ProposalRejectAPIView,
)
from chore_sync.api.messaging_router import GroupMessageListAPIView, MarkReadAPIView
from chore_sync.api.preference_router import GroupPreferenceListAPIView, TaskPreferenceAPIView
from chore_sync.api.notification_router import (
    NotificationListAPIView,
    NotificationHistoryAPIView,
    NotificationReadAPIView,
    NotificationDismissAPIView,
    NotificationPreferenceAPIView,
    PushTokenAPIView,
)
from chore_sync.api.outlook_calendar_router import (
    OutlookCalendarAuthURLAPIView,
    OutlookCalendarCallbackAPIView,
    OutlookCalendarListAPIView,
    OutlookCalendarSelectAPIView,
    OutlookCalendarSyncAPIView,
    OutlookCalendarWebhookAPIView,
)
from chore_sync.api.chatbot_router import ChatbotMessageAPIView, ChatbotSessionListAPIView
from chore_sync.api.jwt_views import (
    JWTObtainTokenAPIView,
    GoogleMobileLoginAPIView,
    MicrosoftMobileLoginAPIView,
    TokenRefreshView,
    TokenVerifyView,
)

from chore_sync.api.group_router import (
    GroupListCreateAPIView,
    GroupDetailAPIView,
    GroupJoinByCodeAPIView,
    GroupInviteAPIView,
    GroupMembersAPIView,
    GroupAssignmentMatrixAPIView,
    GroupSettingsAPIView,
    GroupLeaderboardAPIView,
    GroupLeaveAPIView,
)
from chore_sync.api.views import (
    SignupAPIView,
    LoginAPIView,
    ResendVerificationAPIView,
    VerifyEmailAPIView,
    LogoutAPIView,
    UpdateEmailAPIView,
    ProfileAPIView,
    AvatarUploadAPIView,
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
    CalendarStatusAPIView,
    UserCalendarListAPIView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT auth — React Native mobile client
    path('api/auth/token/', JWTObtainTokenAPIView.as_view(), name='jwt-obtain'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='jwt-refresh'),
    path('api/auth/token/verify/', TokenVerifyView.as_view(), name='jwt-verify'),
    # Session auth — Vue web app
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
    # Mobile JWT SSO — returns access+refresh instead of a session cookie
    path('api/auth/google/mobile/', GoogleMobileLoginAPIView.as_view(), name='google-mobile-login'),
    path('api/auth/microsoft/mobile/', MicrosoftMobileLoginAPIView.as_view(), name='microsoft-mobile-login'),
    path('api/profile/', ProfileAPIView.as_view(), name='profile'),
    path('api/users/me/avatar/', AvatarUploadAPIView.as_view(), name='avatar-upload'),
    path('api/events/', EventsAPIView.as_view(), name='events'),
    path('api/events/<int:pk>/', EventDetailAPIView.as_view(), name='event-detail'),
    path('api/calendar/google/list/', GoogleCalendarListAPIView.as_view(), name='google-cal-list'),
    path('api/calendar/google/select/', GoogleCalendarSelectAPIView.as_view(), name='google-cal-select'),
    path('api/calendar/google/auth-url/', GoogleCalendarAuthURLAPIView.as_view(), name='google-cal-auth-url'),
    path('api/calendar/google/callback/', GoogleCalendarCallbackAPIView.as_view(), name='google-cal-callback'),
    path('api/calendar/google/sync/', GoogleCalendarSyncAPIView.as_view(), name='google-cal-sync'),
    path('api/calendar/google/webhook/', GoogleCalendarWebhookAPIView.as_view(), name='google-cal-webhook'),
    path('api/calendar/outlook/auth-url/', OutlookCalendarAuthURLAPIView.as_view(), name='outlook-cal-auth-url'),
    path('api/calendar/outlook/callback/', OutlookCalendarCallbackAPIView.as_view(), name='outlook-cal-callback'),
    path('api/calendar/outlook/list/', OutlookCalendarListAPIView.as_view(), name='outlook-cal-list'),
    path('api/calendar/outlook/select/', OutlookCalendarSelectAPIView.as_view(), name='outlook-cal-select'),
    path('api/calendar/outlook/sync/', OutlookCalendarSyncAPIView.as_view(), name='outlook-cal-sync'),
    path('api/calendar/outlook/webhook/', OutlookCalendarWebhookAPIView.as_view(), name='outlook-cal-webhook'),
    path('api/calendar/status/', CalendarStatusAPIView.as_view(), name='calendar-status'),
    path('api/calendars/', UserCalendarListAPIView.as_view(), name='user-calendars'),
    path('api/events/stream/', EventStreamAPIView.as_view(), name='event-stream'),
    path('api/groups/', GroupListCreateAPIView.as_view(), name='group-list-create'),
    path('api/groups/join/', GroupJoinByCodeAPIView.as_view(), name='group-join-by-code'),
    path('api/groups/<uuid:pk>/', GroupDetailAPIView.as_view(), name='group-detail'),
    path('api/groups/<uuid:pk>/invite/', GroupInviteAPIView.as_view(), name='group-invite'),
    path('api/groups/<uuid:pk>/members/', GroupMembersAPIView.as_view(), name='group-members'),
    path('api/groups/<uuid:pk>/assignment-matrix/', GroupAssignmentMatrixAPIView.as_view(), name='group-assignment-matrix'),
    path('api/groups/<uuid:pk>/settings/', GroupSettingsAPIView.as_view(), name='group-settings'),
    path('api/groups/<uuid:pk>/leaderboard/', GroupLeaderboardAPIView.as_view(), name='group-leaderboard'),
    path('api/groups/<uuid:pk>/leave/', GroupLeaveAPIView.as_view(), name='group-leave'),
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
    path('api/tasks/<int:pk>/upload-proof/', TaskPhotoProofAPIView.as_view(), name='task-upload-proof'),
    path('api/tasks/<int:pk>/accept-suggestion/', TaskAcceptSuggestionAPIView.as_view(), name='task-accept-suggestion'),
    path('api/tasks/<int:pk>/decline-suggestion/', TaskDeclineSuggestionAPIView.as_view(), name='task-decline-suggestion'),
    path('api/tasks/<int:pk>/assignment-breakdown/', TaskOccurrenceAssignmentBreakdownAPIView.as_view(), name='task-assignment-breakdown'),
    path('api/users/me/pending-swaps/', PendingSwapsAPIView.as_view(), name='user-pending-swaps'),
    path('api/tasks/<int:pk>/list-marketplace/', TaskListMarketplaceAPIView.as_view(), name='task-list-marketplace'),
    path('api/groups/<uuid:pk>/marketplace/', GroupMarketplaceListAPIView.as_view(), name='group-marketplace'),
    path('api/marketplace/<int:pk>/claim/', MarketplaceClaimAPIView.as_view(), name='marketplace-claim'),
    path('api/marketplace/<int:pk>/cancel/', MarketplaceCancelAPIView.as_view(), name='marketplace-cancel'),
    path('api/users/me/stats/', UserStatsAPIView.as_view(), name='user-stats'),
    path('api/users/me/badges/', UserBadgesAPIView.as_view(), name='user-badges'),
    path('api/groups/<uuid:pk>/stats/', GroupStatsAPIView.as_view(), name='group-stats'),
    path('api/groups/<uuid:pk>/proposals/', GroupProposalListCreateAPIView.as_view(), name='group-proposals'),
    path('api/proposals/<int:pk>/approve/', ProposalApproveAPIView.as_view(), name='proposal-approve'),
    path('api/proposals/<int:pk>/reject/', ProposalRejectAPIView.as_view(), name='proposal-reject'),
    path('api/notifications/', NotificationListAPIView.as_view(), name='notification-list'),
    path('api/notifications/history/', NotificationHistoryAPIView.as_view(), name='notification-history'),
    path('api/notifications/<int:pk>/read/', NotificationReadAPIView.as_view(), name='notification-read'),
    path('api/notifications/<int:pk>/dismiss/', NotificationDismissAPIView.as_view(), name='notification-dismiss'),
    path('api/users/me/notification-preferences/', NotificationPreferenceAPIView.as_view(), name='notification-preferences'),
    path('api/push-token/', PushTokenAPIView.as_view(), name='push-token'),
    path('api/groups/<uuid:pk>/messages/', GroupMessageListAPIView.as_view(), name='group-messages'),
    path('api/groups/<uuid:pk>/messages/read/', MarkReadAPIView.as_view(), name='group-messages-read'),
    path('api/assistant/', ChatbotMessageAPIView.as_view(), name='assistant'),
    path('api/assistant/sessions/', ChatbotSessionListAPIView.as_view(), name='assistant-sessions'),
    path('api/groups/<uuid:pk>/my-preferences/', GroupPreferenceListAPIView.as_view(), name='group-my-preferences'),
    path('api/task-templates/<int:pk>/my-preference/', TaskPreferenceAPIView.as_view(), name='task-template-my-preference'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
