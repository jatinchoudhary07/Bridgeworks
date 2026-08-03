from django.contrib import admin

from .models import Account, JournalEntry, JournalItem, Ledger, Outstanding, PendingExpense


@admin.register(Ledger)
class LedgerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'type')
    search_fields = ('name',)
    list_filter = ('type',)


class JournalItemInline(admin.TabularInline):
    model = JournalItem
    extra = 0


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'created_at')
    search_fields = ('description',)
    inlines = [JournalItemInline]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'type', 'balance')
    search_fields = ('name',)
    list_filter = ('type',)


@admin.register(PendingExpense)
class PendingExpenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'employee_name', 'amount', 'category', 'status', 'source_id', 'created_at')
    list_filter = ('status', 'source')
    search_fields = ('employee_name', 'source_id', 'description')
    readonly_fields = ('source_id', 'source', 'journal_entry', 'created_at', 'updated_at')


@admin.register(Outstanding)
class OutstandingAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'party_name', 'amount', 'status', 'due_date', 'created_at')
    list_filter = ('type', 'status')
    search_fields = ('party_name', 'description')
    date_hierarchy = 'created_at'
