from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from accounts.forms import LoginForm
from accounts.models import User


def is_admin(user):
    return user.is_authenticated and user.role in ['admin', 'ict']


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        from accounts.models import Notification
        Notification.objects.create(
            user=user,
            title="Welcome back!",
            message=f"Hello {user.first_name or user.username}, welcome to the SEEPO Dashboard."
        )
        return redirect(request.GET.get('next', 'dashboard'))
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
@user_passes_test(is_admin)
def user_list(request):
    users = User.objects.all().order_by('role', 'username')
    return render(request, 'accounts/user_list.html', {'users': users})


@login_required
@user_passes_test(is_admin)
def user_create(request):
    from accounts.forms import UserCreationForm
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f'User "{user.username}" created successfully.')
        return redirect('user_list')
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'Create User'})


@login_required
@user_passes_test(is_admin)
def user_edit(request, pk):
    from accounts.forms import UserEditForm
    user = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'User "{user.username}" updated.')
        return redirect('user_list')
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'Edit User', 'edit_user': user})


@login_required
@user_passes_test(is_admin)
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot delete yourself.")
        return redirect('user_list')
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" deleted.')
        return redirect('user_list')
    return render(request, 'accounts/user_confirm_delete.html', {'user_to_delete': user})


@login_required
@user_passes_test(is_admin)
def user_password_reset(request, pk):
    from accounts.forms import PasswordResetForm
    user = get_object_or_404(User, pk=pk)
    form = PasswordResetForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user.set_password(form.cleaned_data['new_password'])
        user.save()
        messages.success(request, f'Password for "{user.username}" has been reset.')
        return redirect('user_list')
    return render(request, 'accounts/password_reset_form.html', {'form': form, 'edit_user': user})


@login_required
def profile_view(request):
    from accounts.forms import ProfileUpdateForm
    form = ProfileUpdateForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def settings_view(request):
    return render(request, 'accounts/settings.html')


@login_required
def search_view(request):
    query = request.GET.get('q', '')
    if query:
        from groups.models import Group
        from members.models import Member
        groups = Group.objects.filter(name__icontains=query)
        members = Member.objects.filter(name__icontains=query)
    else:
        groups = []
        members = []
    return render(request, 'accounts/search_results.html', {
        'groups': groups, 'members': members, 'query': query
    })


@login_required
def notification_list(request):
    from accounts.models import Notification

    if request.method == 'POST' and request.POST.get('action') == 'mark_all_read':
        updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.success(request, f'Marked {updated} notification(s) as read.')
        return redirect('notification_list')

    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(
        request,
        'accounts/notification_list.html',
        {
            'notifications': notifications,
            'unread_total': notifications.filter(is_read=False).count(),
        },
    )


@login_required
def mark_notification_read(request, pk):
    from accounts.models import Notification
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.url:
        return redirect(notification.url)
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))
