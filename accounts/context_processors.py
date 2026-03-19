from accounts.models import Notification

def notifications(request):
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False)[:5]
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {
            'unread_notifications': unread,
            'unread_notifications_count': unread_count
        }
    return {
        'unread_notifications': [],
        'unread_notifications_count': 0
    }
