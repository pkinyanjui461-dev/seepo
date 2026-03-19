from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from groups.models import Group
from groups.forms import GroupForm
from members.models import Member
from finance.models import MonthlyForm
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


@login_required
def group_list(request):
    groups = Group.objects.all()
    return render(request, 'groups/group_list.html', {'groups': groups})


@login_required
def group_create(request):
    form = GroupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        group = form.save()
        messages.success(request, f'Group "{group.name}" created successfully.')
        return redirect('group_detail', pk=group.pk)
    return render(request, 'groups/group_form.html', {'form': form, 'title': 'Create Group'})


@login_required
def group_detail(request, pk):
    group = get_object_or_404(Group, pk=pk)
    members = group.member_set.filter(is_active=True)
    monthly_forms = group.monthly_forms.all()
    tab = request.GET.get('tab', 'members')
    return render(request, 'groups/group_detail.html', {
        'group': group,
        'members': members,
        'monthly_forms': monthly_forms,
        'active_tab': tab,
    })


@login_required
def group_edit(request, pk):
    group = get_object_or_404(Group, pk=pk)
    form = GroupForm(request.POST or None, instance=group)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Group "{group.name}" updated.')
        return redirect('group_detail', pk=group.pk)
    return render(request, 'groups/group_form.html', {'form': form, 'title': 'Edit Group', 'group': group})


@login_required
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        name = group.name
        group.delete()
        messages.success(request, f'Group "{name}" deleted.')
        return redirect('group_list')
    return render(request, 'groups/group_confirm_delete.html', {'group': group})


@login_required
def diary_list(request):
    """View to display the diary/schedule for all groups."""
    from groups.models import DiaryEntry
    
    # Ensure every group has a DiaryEntry created
    groups = Group.objects.all().order_by('name')
    for g in groups:
        if not hasattr(g, 'diary'):
            DiaryEntry.objects.create(group=g)
            
    diaries = DiaryEntry.objects.all().select_related('group').order_by('group__name')
    return render(request, 'groups/diary_list.html', {'diaries': diaries})


@csrf_exempt
@require_POST
@login_required
def api_diary_update(request, pk):
    """AJAX endpoint to update DiaryEntry fields."""
    from groups.models import DiaryEntry
    diary = get_object_or_404(DiaryEntry, pk=pk)
    
    try:
        data = json.loads(request.body)
        field = data.get('field')
        value = data.get('value')
        
        if field and hasattr(diary, field.lower()):
            setattr(diary, field.lower(), value)
            diary.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Invalid field'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
