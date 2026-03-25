from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from members.models import Member
from members.forms import MemberForm
from groups.models import Group


@login_required
def member_list(request, group_pk):
    group = get_object_or_404(Group, pk=group_pk)
    members = group.member_set.all()
    return render(request, 'members/member_list.html', {'group': group, 'members': members})


@login_required
def member_create(request, group_pk):
    group = get_object_or_404(Group, pk=group_pk)
    form = MemberForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        member = form.save(commit=False)
        member.group = group
        try:
            member.save()
            messages.success(request, f'Member "{member.name}" added to {group.name}.')
            return redirect('group_detail', pk=group.pk)
        except IntegrityError:
            messages.error(
                request,
                f'A member with number {member.member_number} already exists in {group.name}. '
                f'Please use a different member number.'
            )
    return render(request, 'members/member_form.html', {
        'form': form, 'group': group, 'title': 'Add Member'
    })


@login_required
def member_edit(request, pk):
    member = get_object_or_404(Member, pk=pk)
    group = member.group
    form = MemberForm(request.POST or None, instance=member)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, f'Member "{member.name}" updated.')
            return redirect('group_detail', pk=group.pk)
        except IntegrityError:
            messages.error(
                request,
                f'A member with number {form.cleaned_data.get("member_number")} already exists in {group.name}. '
                f'Please use a different member number.'
            )
    return render(request, 'members/member_form.html', {
        'form': form, 'group': group, 'title': 'Edit Member'
    })


@login_required
def member_delete(request, pk):
    member = get_object_or_404(Member, pk=pk)
    group = member.group
    if request.method == 'POST':
        name = member.name
        member.delete()
        messages.success(request, f'Member "{name}" removed.')
        return redirect('group_detail', pk=group.pk)
    return render(request, 'members/member_confirm_delete.html', {'member': member, 'group': group})
