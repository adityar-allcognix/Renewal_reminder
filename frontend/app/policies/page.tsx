'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Plus, Calendar, Mail, Phone, MessageSquare } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { DataTable } from '@/components/DataTable';
import { api } from '@/lib/api';
import { Policy, Customer } from '@/lib/types';
import CustomerDetailsModal from '@/components/CustomerDetailsModal';

export default function PoliciesPage() {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const pageSize = 10;

  const { data, isLoading } = useQuery({
    queryKey: ['policies', page, searchQuery],
    queryFn: () => api.getPolicies(page, pageSize),
  });

  // Filter policies based on search query
  const filteredData = (data?.items || []).filter((policy: Policy) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      policy.policy_number.toLowerCase().includes(query) ||
      policy.product_type?.toLowerCase().includes(query) ||
      policy.customer?.full_name?.toLowerCase().includes(query) ||
      policy.customer?.email?.toLowerCase().includes(query)
    );
  });

  const handleCustomerClick = (policy: Policy) => {
    if (policy.customer) {
      setSelectedCustomer(policy.customer);
      setIsModalOpen(true);
    } else {
      alert('Customer details not available for this policy.');
    }
  };

  const displayData = filteredData;
  const totalItems = filteredData.length;

  const columns = [
    {
      key: 'policy_number',
      title: 'Policy Number',
      render: (policy: Policy) => (
        <button 
          onClick={() => handleCustomerClick(policy)}
          className="font-medium text-primary-600 hover:text-primary-800 hover:underline focus:outline-none"
        >
          {policy.policy_number}
        </button>
      ),
    },
    {
      key: 'product_type',
      title: 'Product',
    },
    {
      key: 'premium_amount',
      title: 'Premium',
      render: (policy: Policy) => (
        <span>${policy.premium_amount.toLocaleString()}</span>
      ),
    },
    {
      key: 'end_date',
      title: 'Expiry Date',
      render: (policy: Policy) => (
        <div className="flex items-center space-x-2">
          <Calendar className="w-4 h-4 text-gray-400" />
          <span>{new Date(policy.end_date).toLocaleDateString()}</span>
        </div>
      ),
    },
    {
      key: 'days_until_expiry',
      title: 'Days Left',
      render: (policy: Policy) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          policy.days_until_expiry <= 7 ? 'bg-red-100 text-red-700' :
          policy.days_until_expiry <= 30 ? 'bg-yellow-100 text-yellow-700' :
          'bg-green-100 text-green-700'
        }`}>
          {policy.days_until_expiry} days
        </span>
      ),
    },
    {
      key: 'status',
      title: 'Status',
      render: (policy: Policy) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${
          policy.status === 'active' ? 'bg-green-100 text-green-700' :
          policy.status === 'expired' ? 'bg-red-100 text-red-700' :
          policy.status === 'renewed' ? 'bg-blue-100 text-blue-700' :
          'bg-gray-100 text-gray-700'
        }`}>
          {policy.status}
        </span>
      ),
    },
    {
      key: 'renewal_status',
      title: 'Renewal Status',
      render: (policy: Policy) => (
        <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${
          policy.renewal_status === 'confirmed' ? 'bg-green-100 text-green-700' :
          policy.renewal_status === 'notified' ? 'bg-blue-100 text-blue-700' :
          policy.renewal_status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
          'bg-red-100 text-red-700'
        }`}>
          {policy.renewal_status}
        </span>
      ),
    },
  ];

  return (
    <DashboardLayout title="Policies" subtitle="Manage customer policies and renewals">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <select className="px-4 py-2 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="expired">Expired</option>
            <option value="renewed">Renewed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select className="px-4 py-2 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Products</option>
            <option value="term-life">Term Life</option>
            <option value="health">Health Insurance</option>
            <option value="auto">Auto Insurance</option>
        </select>
      </div>
    </div>      <DataTable
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
    </DashboardLayout>
  );
}
