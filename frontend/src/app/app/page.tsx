import ProtectedLayout from '@/components/ProtectedLayout'
import {
    Activity,
    Heart,
    BookOpen,
    Calendar,
    TrendingUp,
    ArrowRight,
    Sparkles
} from 'lucide-react'

/**
 * User Dashboard Page (/app)
 * Main authenticated area for users
 * Shows overview of vitals, journal, upcoming sessions, etc.
 */
export default function UserDashboard() {
    return (
        <ProtectedLayout userType="user">
            {/* Welcome Section */}
            <div className="mb-8">
                <h1 className="text-3xl font-display font-bold text-gray-900 mb-2">
                    Welcome back, John! 👋
                </h1>
                <p className="text-gray-600">
                    Here's your wellbeing overview for today
                </p>
            </div>

            {/* Quick Stats */}
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div className="card">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-primary-100 p-3 rounded-xl">
                            <Activity className="w-6 h-6 text-primary-700" />
                        </div>
                        <span className="text-xs text-green-600 font-medium">+5% this week</span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900 mb-1">72 BPM</div>
                    <div className="text-sm text-gray-600">Average Heart Rate</div>
                </div>

                <div className="card">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-secondary-100 p-3 rounded-xl">
                            <BookOpen className="w-6 h-6 text-secondary-700" />
                        </div>
                        <span className="text-xs text-green-600 font-medium">7 day streak</span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900 mb-1">28</div>
                    <div className="text-sm text-gray-600">Journal Entries</div>
                </div>

                <div className="card">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-accent-100 p-3 rounded-xl">
                            <Heart className="w-6 h-6 text-accent-700" />
                        </div>
                        <span className="text-xs text-gray-600">This month</span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900 mb-1">3</div>
                    <div className="text-sm text-gray-600">Sessions Completed</div>
                </div>

                <div className="card">
                    <div className="flex items-center justify-between mb-4">
                        <div className="bg-green-100 p-3 rounded-xl">
                            <TrendingUp className="w-6 h-6 text-green-700" />
                        </div>
                        <span className="text-xs text-green-600 font-medium">Improving</span>
                    </div>
                    <div className="text-2xl font-bold text-gray-900 mb-1">Good</div>
                    <div className="text-sm text-gray-600">Overall Wellbeing</div>
                </div>
            </div>

            {/* Main Content Grid */}
            <div className="grid lg:grid-cols-3 gap-6">
                {/* Left Column - 2/3 width */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Today's Mood */}
                    <div className="card">
                        <h2 className="text-xl font-display font-semibold text-gray-900 mb-4">
                            How are you feeling today?
                        </h2>
                        <div className="flex gap-3">
                            {['😊', '😐', '😔', '😰', '😡'].map((emoji, i) => (
                                <button
                                    key={i}
                                    className="flex-1 p-4 text-4xl hover:bg-gray-50 rounded-xl border-2 border-gray-200 hover:border-primary-500 transition-all"
                                >
                                    {emoji}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Quick Actions */}
                    <div className="card">
                        <h2 className="text-xl font-display font-semibold text-gray-900 mb-4">
                            Quick Actions
                        </h2>
                        <div className="grid sm:grid-cols-2 gap-4">
                            <button className="flex items-center gap-3 p-4 bg-gradient-to-br from-primary-50 to-primary-100 rounded-xl hover:shadow-md transition-all group">
                                <div className="bg-primary-600 p-2 rounded-lg">
                                    <Activity className="w-5 h-5 text-white" />
                                </div>
                                <div className="text-left flex-1">
                                    <div className="font-semibold text-gray-900">Scan Vitals</div>
                                    <div className="text-sm text-gray-600">Check your health</div>
                                </div>
                                <ArrowRight className="w-5 h-5 text-primary-600 group-hover:translate-x-1 transition-transform" />
                            </button>

                            <button className="flex items-center gap-3 p-4 bg-gradient-to-br from-secondary-50 to-secondary-100 rounded-xl hover:shadow-md transition-all group">
                                <div className="bg-secondary-600 p-2 rounded-lg">
                                    <BookOpen className="w-5 h-5 text-white" />
                                </div>
                                <div className="text-left flex-1">
                                    <div className="font-semibold text-gray-900">Write Journal</div>
                                    <div className="text-sm text-gray-600">Express yourself</div>
                                </div>
                                <ArrowRight className="w-5 h-5 text-secondary-600 group-hover:translate-x-1 transition-transform" />
                            </button>

                            <button className="flex items-center gap-3 p-4 bg-gradient-to-br from-accent-50 to-accent-100 rounded-xl hover:shadow-md transition-all group">
                                <div className="bg-accent-600 p-2 rounded-lg">
                                    <Sparkles className="w-5 h-5 text-white" />
                                </div>
                                <div className="text-left flex-1">
                                    <div className="font-semibold text-gray-900">AI Assistant</div>
                                    <div className="text-sm text-gray-600">Get support</div>
                                </div>
                                <ArrowRight className="w-5 h-5 text-accent-600 group-hover:translate-x-1 transition-transform" />
                            </button>

                            <button className="flex items-center gap-3 p-4 bg-gradient-to-br from-green-50 to-green-100 rounded-xl hover:shadow-md transition-all group">
                                <div className="bg-green-600 p-2 rounded-lg">
                                    <Calendar className="w-5 h-5 text-white" />
                                </div>
                                <div className="text-left flex-1">
                                    <div className="font-semibold text-gray-900">Book Session</div>
                                    <div className="text-sm text-gray-600">Talk to expert</div>
                                </div>
                                <ArrowRight className="w-5 h-5 text-green-600 group-hover:translate-x-1 transition-transform" />
                            </button>
                        </div>
                    </div>

                    {/* Recent Journal Entries */}
                    <div className="card">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-display font-semibold text-gray-900">
                                Recent Journal Entries
                            </h2>
                            <button className="text-primary-600 text-sm font-medium hover:text-primary-700">
                                View All
                            </button>
                        </div>
                        <div className="space-y-3">
                            {[
                                { date: 'Today', mood: '😊', preview: 'Had a great session with my consultant. Feeling much better about...' },
                                { date: 'Yesterday', mood: '😐', preview: 'Work was stressful but managed to do my breathing exercises...' },
                                { date: '2 days ago', mood: '😊', preview: 'Morning yoga session was amazing! Feeling energized and...' },
                            ].map((entry, i) => (
                                <div key={i} className="p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors cursor-pointer">
                                    <div className="flex items-center gap-3 mb-2">
                                        <span className="text-2xl">{entry.mood}</span>
                                        <span className="text-sm font-medium text-gray-900">{entry.date}</span>
                                    </div>
                                    <p className="text-sm text-gray-600 line-clamp-1">{entry.preview}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Right Column - 1/3 width */}
                <div className="space-y-6">
                    {/* Upcoming Sessions */}
                    <div className="card">
                        <h2 className="text-xl font-display font-semibold text-gray-900 mb-4">
                            Upcoming Sessions
                        </h2>
                        <div className="space-y-3">
                            <div className="p-4 bg-primary-50 border border-primary-200 rounded-xl">
                                <div className="flex items-center gap-3 mb-2">
                                    <div className="w-10 h-10 bg-primary-600 rounded-full flex items-center justify-center text-white font-semibold text-sm">
                                        DR
                                    </div>
                                    <div className="flex-1">
                                        <div className="font-semibold text-gray-900">Dr. Radhika</div>
                                        <div className="text-xs text-gray-600">Wellbeing Consultant</div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 text-sm text-gray-700">
                                    <Calendar className="w-4 h-4" />
                                    <span>Tomorrow, 3:00 PM</span>
                                </div>
                            </div>

                            <button className="w-full btn btn-secondary text-sm">
                                Book New Session
                            </button>
                        </div>
                    </div>

                    {/* Wellness Score */}
                    <div className="card bg-gradient-to-br from-primary-600 to-secondary-600 text-white">
                        <h2 className="text-lg font-display font-semibold mb-4">
                            Your Wellness Score
                        </h2>
                        <div className="text-center py-6">
                            <div className="text-5xl font-bold mb-2">78</div>
                            <div className="text-primary-100 text-sm">Out of 100</div>
                        </div>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <span className="text-primary-100">Physical Health</span>
                                <span className="font-semibold">82%</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-primary-100">Emotional Wellbeing</span>
                                <span className="font-semibold">75%</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-primary-100">Lifestyle</span>
                                <span className="font-semibold">77%</span>
                            </div>
                        </div>
                    </div>

                    {/* Daily Tip */}
                    <div className="card bg-accent-50 border border-accent-200">
                        <div className="flex items-center gap-2 mb-3">
                            <Sparkles className="w-5 h-5 text-accent-600" />
                            <h3 className="font-semibold text-gray-900">Daily Tip</h3>
                        </div>
                        <p className="text-sm text-gray-700">
                            Take 5 minutes today for deep breathing. It can reduce stress and improve focus.
                        </p>
                    </div>
                </div>
            </div>
        </ProtectedLayout>
    )
}
