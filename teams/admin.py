from django.contrib import admin

from .models import Team, TeamMembership


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    raw_id_fields = ('user',)
    readonly_fields = ('joined_at',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'creator', 'is_open', 'member_count', 'created_at')
    search_fields = ('name', 'slug', 'creator__username', 'creator__email')
    list_filter = ('is_open',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TeamMembershipInline]

    @admin.display(description='Active members')
    def member_count(self, obj):
        return obj.active_memberships().count()


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ('team', 'user', 'role', 'joined_at', 'left_at')
    list_filter = ('role',)
    search_fields = ('team__name', 'user__username', 'user__email')
    raw_id_fields = ('user', 'team')
