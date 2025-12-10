'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Send, X, Clock, CheckCircle, AlertCircle, Mail, Phone, MessageSquare } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { DataTable } from '@/components/DataTable';
import { api } from '@/lib/api';
import { Reminder, Customer } from '@/lib/types';
import CustomerDetailsModal from '@/components/CustomerDetailsModal';
import ConfirmationModal from '@/components/ConfirmationModal';

export default function RemindersPage() {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [reminderToSend, setReminderToSend] = useState<string | null>(null);
  const pageSize = 10;
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['reminders', page, searchQuery],
    queryFn: () => api.getReminders(page, pageSize),
  });

  const sendReminderMutation = useMutation({
    mutationFn: (id: string) => api.sendReminder(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminders'] });
      setIsConfirmOpen(false);
      setReminderToSend(null);
      // Optional: Show a toast notification here instead of alert
    },
    onError: (error: any) => {
      alert(`Failed to send reminder: ${error.message}`);
      setIsConfirmOpen(false);
    },
  });

  const handleSendReminder = (id: string) => {
    setReminderToSend(id);
    setIsConfirmOpen(true);
  };

  const handleConfirmSend = () => {
    if (reminderToSend) {
      sendReminderMutation.mutate(reminderToSend);
    }
  };

  const handleCustomerClick = (reminder: Reminder) => {
    if (reminder.policy?.customer) {
      setSelectedCustomer(reminder.policy.customer);
      setIsModalOpen(true);
    } else {
      alert('Customer details not available for this policy.');
    }
  };

  const displayData = data?.items || [];
  const totalItems = data?.total || 0;

  const getChannelIcon = (channel: string) => {
    switch (channel) {
      case 'email':
        return <Mail className="w-4 h-4" />;
      case 'sms':
        return <Phone className="w-4 h-4" />;
      case 'whatsapp':
        return <MessageSquare className="w-4 h-4" />;
      default:
        return <Mail className="w-4 h-4" />;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'sent':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      case 'cancelled':
        return <X className="w-4 h-4 text-gray-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const columns = [
    {
      key: 'policy_id',
      title: 'Policy',
      render: (reminder: Reminder) => (
        <button 
          onClick={() => handleCustomerClick(reminder)}
          className="font-medium text-primary-600 hover:text-primary-800 hover:underline focus:outline-none"
        >
          POL-{reminder.policy_id.substring(0, 8)}...
        </button>
      ),
    },
    {
      key: 'reminder_type',
      title: 'Type',
      render: (reminder: Reminder) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${
          reminder.reminder_type === 'first' ? 'bg-blue-100 text-blue-700' :
          reminder.reminder_type === 'second' ? 'bg-yellow-100 text-yellow-700' :
          reminder.reminder_type === 'final' ? 'bg-red-100 text-red-700' :
          'bg-gray-100 text-gray-700'
        }`}>
          {reminder.reminder_type}
        </span>
      ),
    },
    {
      key: 'channel',
      title: 'Channel',
      render: (reminder: Reminder) => (
        <div className="flex items-center space-x-2">
          <span className="text-gray-400">{getChannelIcon(reminder.channel)}</span>
          <span className="capitalize">{reminder.channel}</span>
        </div>
      ),
    },
    {
      key: 'scheduled_date',
      title: 'Scheduled',
      render: (reminder: Reminder) => (
        <span>{new Date(reminder.scheduled_date).toLocaleString()}</span>
      ),
    },
    {
      key: 'status',
      title: 'Status',
      render: (reminder: Reminder) => (
        <div className="flex items-center space-x-2">
          {getStatusIcon(reminder.status)}
          <span className="capitalize">{reminder.status}</span>
        </div>
      ),
    },
    {
      key: 'response_status',
      title: 'Response',
      render: (reminder: Reminder) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          reminder.response_status === 'responded' ? 'bg-green-100 text-green-700' :
          reminder.response_status === 'clicked' ? 'bg-blue-100 text-blue-700' :
          reminder.response_status === 'opened' ? 'bg-yellow-100 text-yellow-700' :
          'bg-gray-100 text-gray-700'
        }`}>
          {(reminder.response_status || 'no_response').replace('_', ' ')}
        </span>
      ),
    },
    {
      key: 'actions',
      title: 'Actions',
      render: (reminder: Reminder) => (
        <div className="flex items-center space-x-2">
          {reminder.status === 'pending' && (
            <button 
              onClick={() => handleSendReminder(reminder.id)}
              disabled={sendReminderMutation.isPending}
              className="p-1 text-green-600 hover:bg-green-50 rounded disabled:opacity-50"
              title="Send Reminder Now"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <DashboardLayout title="Reminders" subtitle="Manage renewal reminders and notifications">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <select className="px-4 py-2 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="sent">Sent</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select className="px-4 py-2 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Channels</option>
            <option value="email">Email</option>
            <option value="sms">SMS</option>
            <option value="whatsapp">WhatsApp</option>
          </select>
          <select className="px-4 py-2 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Types</option>
            <option value="first">First Reminder</option>
            <option value="second">Second Reminder</option>
            <option value="final">Final Reminder</option>
            <option value="lapsed">Lapsed</option>
          </select>
        </div>
        <button className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors">
          <Plus className="w-4 h-4 mr-2" />
          Create Reminder
        </button>
      </div>

      <DataTable
        data={displayData}
        columns={columns}
        totalItems={totalItems}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onSearch={setSearchQuery}
        isLoading={isLoading}
      />

      <CustomerDetailsModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        customer={selectedCustomer}
      />

      <ConfirmationModal
        isOpen={isConfirmOpen}
        onClose={() => setIsConfirmOpen(false)}
        onConfirm={handleConfirmSend}
        title="Send Reminder"
        message="Are you sure you want to send this reminder now? This action cannot be undone."
        confirmText="Send Now"
        isProcessing={sendReminderMutation.isPending}
      />
    </DashboardLayout>
  );
}
