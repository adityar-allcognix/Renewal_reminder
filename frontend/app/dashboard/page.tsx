'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { 
  Users, 
  FileText, 
  Bell, 
  TrendingUp, 
  AlertCircle,
  CheckCircle,
  Clock,
  Mail,
  Loader2
} from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { StatsCard } from '@/components/StatsCard';
import { api } from '@/lib/api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444'];

export default function DashboardPage() {
  const router = useRouter();
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.getDashboardStats(),
  });

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: () => api.getAnalytics(),
  });

  if (statsLoading || analyticsLoading) {
    return (
      <DashboardLayout title="Dashboard" subtitle="Overview of your renewal management system">
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      </DashboardLayout>
    );
  }

  if (!stats) {
    return (
      <DashboardLayout title="Dashboard" subtitle="Overview of your renewal management system">
        <div className="text-center py-12">
          <p className="text-gray-500">Failed to load dashboard data.</p>
        </div>
      </DashboardLayout>
    );
  }

  // Transform analytics data for charts if available
  // Note: Backend currently returns summary stats, not time-series.
  // We will hide the charts until backend supports time-series data.
  
  return (
    <DashboardLayout title="Dashboard" subtitle="Overview of your renewal management system">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatsCard
          title="Total Customers"
          value={stats.total_customers.toLocaleString()}
          change="Active Database Records"
          changeType="neutral"
          icon={Users}
          iconColor="text-blue-600"
          iconBgColor="bg-blue-100"
        />
        <StatsCard
          title="Active Policies"
          value={stats.active_policies.toLocaleString()}
          change="Currently Active"
          changeType="positive"
          icon={FileText}
          iconColor="text-green-600"
          iconBgColor="bg-green-100"
        />
        <StatsCard
          title="Pending Renewals"
          value={stats.pending_renewals}
          change="Action Required"
          changeType="neutral"
          icon={Clock}
          iconColor="text-yellow-600"
          iconBgColor="bg-yellow-100"
        />
        <StatsCard
          title="Renewal Rate"
          value={`${stats.renewal_rate}%`}
          change="Conversion Rate"
          changeType="positive"
          icon={TrendingUp}
          iconColor="text-purple-600"
          iconBgColor="bg-purple-100"
        />
      </div>

      {/* Charts Row - Hidden until backend supports time-series */}
      {/* 
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        ... Charts code ...
      </div>
      */}

      {/* Recent Activity & Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Reminders - Placeholder until API endpoint exists */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Reminder Statistics</h3>
          <div className="space-y-4">
             <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-500">Sent Today</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.reminders_sent_today}</p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-500">Pending</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.reminders_pending}</p>
                </div>
             </div>
             {analytics && (
               <div className="mt-4">
                 <h4 className="text-sm font-medium text-gray-700 mb-2">Delivery Performance</h4>
                 <div className="flex items-center justify-between text-sm text-gray-600 border-t pt-2">
                    <span>Delivered: {analytics.reminder_stats.delivered}</span>
                    <span>Failed: {analytics.reminder_stats.failed}</span>
                    <span>Rate: {analytics.reminder_stats.delivery_rate}%</span>
                 </div>
               </div>
             )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
          <div className="grid grid-cols-2 gap-4">
            <button 
              onClick={() => router.push('/reminders')}
              className="p-4 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors text-left"
            >
              <Bell className="w-6 h-6 text-primary-600 mb-2" />
              <p className="font-medium text-gray-900">Send Reminders</p>
              <p className="text-sm text-gray-500">{stats.reminders_pending} pending</p>
            </button>
            <button 
              onClick={() => router.push('/policies?filter=expiring')}
              className="p-4 bg-green-50 rounded-lg hover:bg-green-100 transition-colors text-left"
            >
              <FileText className="w-6 h-6 text-green-600 mb-2" />
              <p className="font-medium text-gray-900">View Expiring</p>
              <p className="text-sm text-gray-500">{stats.expiring_soon} soon</p>
            </button>
            <button 
              onClick={() => router.push('/customers')}
              className="p-4 bg-yellow-50 rounded-lg hover:bg-yellow-100 transition-colors text-left"
            >
              <Users className="w-6 h-6 text-yellow-600 mb-2" />
              <p className="font-medium text-gray-900">Engagement</p>
              <p className="text-sm text-gray-500">Avg Score: {stats.avg_engagement_score}</p>
            </button>
            <button 
              onClick={() => router.push('/analytics')}
              className="p-4 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors text-left"
            >
              <TrendingUp className="w-6 h-6 text-purple-600 mb-2" />
              <p className="font-medium text-gray-900">View Reports</p>
              <p className="text-sm text-gray-500">Analytics</p>
            </button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
