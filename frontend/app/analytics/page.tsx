'use client';

import { useQuery } from '@tanstack/react-query';
import { Calendar, RefreshCw, Loader2 } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { api } from '@/lib/api';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export default function AnalyticsPage() {
  const { data: analytics, isLoading, refetch } = useQuery({
    queryKey: ['analytics'],
    queryFn: () => api.getAnalytics(),
  });

  if (isLoading) {
    return (
      <DashboardLayout title="Analytics" subtitle="Detailed performance metrics and insights">
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      </DashboardLayout>
    );
  }

  if (!analytics) {
    return (
      <DashboardLayout title="Analytics" subtitle="Detailed performance metrics and insights">
        <div className="text-center py-12">
          <p className="text-gray-500">No analytics data available.</p>
        </div>
      </DashboardLayout>
    );
  }

  const reminderData = [
    { name: 'Sent', value: analytics.reminder_stats.total_sent },
    { name: 'Delivered', value: analytics.reminder_stats.delivered },
    { name: 'Failed', value: analytics.reminder_stats.failed },
    { name: 'Pending', value: analytics.reminder_stats.pending },
  ];

  const conversionData = [
    { name: 'Due', value: analytics.conversion_stats.policies_due },
    { name: 'Renewed', value: analytics.conversion_stats.renewed },
    { name: 'Lapsed', value: analytics.conversion_stats.lapsed },
  ];

  return (
    <DashboardLayout title="Analytics" subtitle="Detailed performance metrics and insights">
      {/* Controls */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 bg-white rounded-lg border border-gray-200 px-4 py-2">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">
              {new Date(analytics.period_start).toLocaleDateString()} - {new Date(analytics.period_end).toLocaleDateString()}
            </span>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => refetch()}
            className="flex items-center px-4 py-2 text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm p-6 text-center">
          <p className="text-3xl font-bold text-primary-600">
            {(analytics.conversion_stats.conversion_rate * 100).toFixed(1)}%
          </p>
          <p className="text-sm text-gray-500 mt-1">Conversion Rate</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6 text-center">
          <p className="text-3xl font-bold text-green-600">
            {(analytics.reminder_stats.delivery_rate * 100).toFixed(1)}%
          </p>
          <p className="text-sm text-gray-500 mt-1">Delivery Rate</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6 text-center">
          <p className="text-3xl font-bold text-yellow-600">
            {(analytics.engagement_stats.positive_feedback_rate * 100).toFixed(1)}%
          </p>
          <p className="text-sm text-gray-500 mt-1">Positive Feedback</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6 text-center">
          <p className="text-3xl font-bold text-purple-600">
            {analytics.engagement_stats.avg_response_time_ms}ms
          </p>
          <p className="text-sm text-gray-500 mt-1">Avg Response Time</p>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Reminder Stats */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Reminder Status</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={reminderData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#2563eb" name="Count" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Conversion Stats */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Renewal Conversion</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={conversionData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#10b981" name="Count" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
