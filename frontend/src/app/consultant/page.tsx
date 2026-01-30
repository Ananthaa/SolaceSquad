import ProtectedLayout from '@/components/ProtectedLayout'
import {
    Users,
    Calendar,
    TrendingUp,
    DollarSign,
    Clock,
    Star,
    ArrowRight,
    MessageSquare
} from 'lucide-react'

/**
 * Consultant Dashboard Page (/consultant)
 * Main authenticated area for consultants
 * Shows client overview, schedule, earnings, etc.
 */
export default function ConsultantDashboard() {
    return (
        <ProtectedLayout userType="consultant">
            {/* Welcome Section */}
            <div className="mb-8">
                <h1 className="text-3xl font-display font-bold text-gray-900 mb-2">
                    Welcome back, Dr. Radhika! 👋
                </h1>
                <p className="text-gray-600">
                    You have 3 sessions scheduled today
                </p>
            </div>

            {/* Quick Stats */}
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div className="card">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-primary-100 p-3 rounded-xl">
                            <Users className="w-6 h-6 text-primary-700" />
                        </div>
                        <span className="text-xs text-green-600 font-medium">+3 this week</span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900 mb-1">24</div>
                    <div className="text-sm text-gray-600">Active Clients</div>
                </div>

                <div className="card">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-secondary-100 p-3 rounded-xl">
                            <Calendar className="w-6 h-6 text-secondary-700" />
                        </div>
                        <span className="text-xs text-gray-600">This week</span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900 mb-1">12</div>
                    <div className="text-sm text-gray-600">Sessions Scheduled</div>
                </div>

                <div className="card">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-accent-100 p-3 rounded-xl">
                            <DollarSign className="w-6 h-6 text-accent-700" />
                        </div>
                        <span className="text-xs text-green-600 font-medium">+12% vs last month</span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900 mb-1">₹45,000</div>
                    <div className="text-sm text-gray-600">This Month</div>
                </div>

                <div className="card">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-green-100 p-3 rounded-xl">
                            <Star className="w-6 h-6 text-green-700" />
                        </div>
                        <span className="text-xs text-gray-600">From 18 reviews</span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900 mb-1">4.9</div>
                    <div className="text-sm text-gray-600">Average Rating</div>
                </div>
            </div>

            {/* Main Content Grid */}
            <div className="grid lg:grid-cols-3 gap-6">
                {/* Left Column - 2/3 width */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Today's Schedule */}
                    <div className="card">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-display font-semibold text-gray-900">
                                Today's Schedule
                            </h2>
                            <button className="text-primary-600 text-sm font-medium hover:text-primary-700">
                                View Calendar
                            </button>
                        </div>
                        <div className="space-y-3">
                            {[
                                { time: '10:00 AM', client: 'Priya Sharma', type: 'Virtual Consultation', status: 'upcoming' },
                                { time: '2:00 PM', client: 'Rahul Mehta', type: 'Follow-up Session', status: 'upcoming' },
                                { time: '4:30 PM', client: 'Anjali Kumar', type: 'Wellness Plan', status: 'upcoming' },
                            ].map((session, i) => (
                                <div key={i} className="p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 bg-gradient-to-br from-primary-400 to-secondary-400 rounded-full flex items-center justify-center text-white font-semibold text-sm">
                                                {session.client.split(' ').map(n => n[0]).join('')}
                                            </div>
                                            <div>
                                                <div className="font-semibold text-gray-900">{session.client}</div>
                                                <div className="text-sm text-gray-600">{session.type}</div>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                                                <Clock className="w-4 h-4" />
                                                {session.time}
                                            </div>
                                            <span className="text-xs text-green-600">Confirmed</span>
                                        </div>
                                    </div>
                                    <div className="flex gap-2">
                                        <button className="flex-1 btn btn-primary text-sm py-2">
                                            Start Session
                                        </button>
                                        <button className="flex-1 btn btn-secondary text-sm py-2">
                                            View Profile
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Recent Client Activity */}
                    <div className="card">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-display font-semibold text-gray-900">
                                Recent Client Activity
                            </h2>
                            <button className="text-primary-600 text-sm font-medium hover:text-primary-700">
                                View All
                            </button>
                        </div>
                        <div className="space-y-3">
                            {[
                                { client: 'Priya S.', action: 'Completed journal entry', time: '2 hours ago', mood: '😊' },
                                { client: 'Rahul M.', action: 'Scheduled follow-up session', time: '5 hours ago', mood: '😐' },
                                { client: 'Anjali K.', action: 'Completed exercise session', time: '1 day ago', mood: '😊' },
                            ].map((activity, i) => (
                                <div key={i} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                                    <span className="text-2xl">{activity.mood}</span>
                                    <div className="flex-1">
                                        <div className="font-medium text-gray-900">{activity.client}</div>
                                        <div className="text-sm text-gray-600">{activity.action}</div>
                                    </div>
                                    <div className="text-xs text-gray-500">{activity.time}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Right Column - 1/3 width */}
                <div className="space-y-6">
                    {/* Pending Messages */}
                    <div className="card">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-display font-semibold text-gray-900">
                                Messages
                            </h2>
                            <span className="bg-red-500 text-white text-xs font-bold px-2 py-1 rounded-full">
                                3
                            </span>
                        </div>
                        <div className="space-y-3">
                            {[
                                { client: 'Priya S.', message: 'Thank you for the session yesterday...', time: '10m ago' },
                                { client: 'Rahul M.', message: 'Can we reschedule tomorrow\'s...', time: '1h ago' },
                            ].map((msg, i) => (
                                <div key={i} className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer">
                                    <div className="flex items-center gap-2 mb-1">
                                        <div className="font-medium text-gray-900 text-sm">{msg.client}</div>
                                        <div className="text-xs text-gray-500">{msg.time}</div>
                                    </div>
                                    <p className="text-sm text-gray-600 line-clamp-1">{msg.message}</p>
                                </div>
                            ))}
                        </div>
                        <button className="w-full btn btn-secondary text-sm mt-3">
                            <MessageSquare className="w-4 h-4" />
                            View All Messages
                        </button>
                    </div>

                    {/* Performance */}
                    <div className="card bg-gradient-to-br from-primary-600 to-secondary-600 text-white">
                        <h2 className="text-lg font-display font-semibold mb-4">
                            This Month's Performance
                        </h2>
                        <div className="space-y-4">
                            <div>
                                <div className="flex justify-between text-sm mb-2">
                                    <span className="text-primary-100">Sessions Completed</span>
                                    <span className="font-semibold">28/30</span>
                                </div>
                                <div className="w-full bg-white/20 rounded-full h-2">
                                    <div className="bg-white rounded-full h-2" style={{ width: '93%' }}></div>
                                </div>
                            </div>

                            <div>
                                <div className="flex justify-between text-sm mb-2">
                                    <span className="text-primary-100">Client Satisfaction</span>
                                    <span className="font-semibold">96%</span>
                                </div>
                                <div className="w-full bg-white/20 rounded-full h-2">
                                    <div className="bg-white rounded-full h-2" style={{ width: '96%' }}></div>
                                </div>
                            </div>

                            <div>
                                <div className="flex justify-between text-sm mb-2">
                                    <span className="text-primary-100">Response Time</span>
                                    <span className="font-semibold">< 2 hours</span>
                                </div>
                                <div className="w-full bg-white/20 rounded-full h-2">
                                    <div className="bg-white rounded-full h-2" style={{ width: '88%' }}></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Quick Actions */}
                    <div className="card">
                        <h2 className="text-lg font-display font-semibold text-gray-900 mb-4">
                            Quick Actions
                        </h2>
                        <div className="space-y-2">
                            <button className="w-full btn btn-primary text-sm justify-start">
                                <Calendar className="w-4 h-4" />
                                Block Time Off
                            </button>
                            <button className="w-full btn btn-secondary text-sm justify-start">
                                <TrendingUp className="w-4 h-4" />
                                View Analytics
                            </button>
                            <button className="w-full btn btn-secondary text-sm justify-start">
                                <Users className="w-4 h-4" />
                                Client Reports
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </ProtectedLayout>
    )
}
