'use client'

import Header from '@/components/Header'
import Footer from '@/components/Footer'
import {
    Heart,
    Shield,
    Users,
    Clock,
    Star,
    CheckCircle,
    ArrowRight,
    Sparkles,
    Brain,
    Activity,
    Calendar,
    MessageCircle
} from 'lucide-react'

/**
 * Marketing Home Page
 * Inspired by SolaceSquad structure with:
 * - Hero section
 * - Why Us section
 * - Services grid
 * - Testimonials
 * - Call-to-action
 */
export default function Home() {
    return (
        <div className="min-h-screen">
            <Header />

            {/* Hero Section */}
            <section className="pt-32 pb-20 bg-gradient-to-br from-primary-50 via-white to-secondary-50">
                <div className="container-custom">
                    <div className="grid lg:grid-cols-2 gap-12 items-center">
                        <div className="animate-slide-up">
                            <div className="inline-flex items-center gap-2 bg-primary-100 text-primary-700 px-4 py-2 rounded-full mb-6">
                                <Sparkles className="w-4 h-4" />
                                <span className="text-sm font-medium">Your Wellbeing Partner</span>
                            </div>

                            <h1 className="text-5xl md:text-6xl font-display font-bold text-gray-900 mb-6 leading-tight">
                                Welcome to{' '}
                                <span className="gradient-text">Soul Squad</span>
                            </h1>

                            <p className="text-xl text-gray-600 mb-8 leading-relaxed">
                                Professional wellbeing consultants trained to support you with empathy, care, and love.
                                Your journey to better emotional wellbeing starts here.
                            </p>

                            <div className="flex flex-col sm:flex-row gap-4">
                                <button className="btn btn-primary text-lg">
                                    Start Your Journey
                                    <ArrowRight className="w-5 h-5" />
                                </button>
                                <button className="btn btn-secondary text-lg">
                                    Book Discovery Call
                                </button>
                            </div>

                            {/* Trust Indicators */}
                            <div className="flex items-center gap-8 mt-12 pt-8 border-t border-gray-200">
                                <div>
                                    <div className="text-3xl font-bold text-gray-900">500+</div>
                                    <div className="text-sm text-gray-600">Happy Clients</div>
                                </div>
                                <div>
                                    <div className="text-3xl font-bold text-gray-900">50+</div>
                                    <div className="text-sm text-gray-600">Expert Consultants</div>
                                </div>
                                <div className="flex items-center gap-1">
                                    <Star className="w-5 h-5 text-accent-500 fill-accent-500" />
                                    <span className="text-3xl font-bold text-gray-900">4.9</span>
                                    <span className="text-sm text-gray-600 ml-1">/5 Rating</span>
                                </div>
                            </div>
                        </div>

                        {/* Hero Image Placeholder */}
                        <div className="relative animate-fade-in">
                            <div className="aspect-square bg-gradient-to-br from-primary-200 to-secondary-200 rounded-3xl shadow-2xl flex items-center justify-center">
                                <Heart className="w-32 h-32 text-white" strokeWidth={1.5} />
                            </div>

                            {/* Floating Cards */}
                            <div className="absolute -top-4 -left-4 bg-white p-4 rounded-2xl shadow-xl">
                                <div className="flex items-center gap-3">
                                    <div className="bg-green-100 p-2 rounded-lg">
                                        <CheckCircle className="w-6 h-6 text-green-600" />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900">100% Confidential</div>
                                        <div className="text-sm text-gray-600">Your privacy matters</div>
                                    </div>
                                </div>
                            </div>

                            <div className="absolute -bottom-4 -right-4 bg-white p-4 rounded-2xl shadow-xl">
                                <div className="flex items-center gap-3">
                                    <div className="bg-primary-100 p-2 rounded-lg">
                                        <Users className="w-6 h-6 text-primary-600" />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900">Expert Support</div>
                                        <div className="text-sm text-gray-600">24/7 Available</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Why Us Section */}
            <section id="why-us" className="section bg-white">
                <div className="container-custom">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl md:text-5xl font-display font-bold text-gray-900 mb-4">
                            Why Choose <span className="gradient-text">Soul Squad</span>?
                        </h2>
                        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
                            We provide personalized support tailored to your unique journey
                        </p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-8">
                        {/* Feature 1 */}
                        <div className="card card-hover text-center">
                            <div className="bg-gradient-to-br from-primary-100 to-primary-200 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6">
                                <Shield className="w-8 h-8 text-primary-700" />
                            </div>
                            <h3 className="text-2xl font-display font-semibold text-gray-900 mb-3">
                                100% Confidential
                            </h3>
                            <p className="text-gray-600">
                                Your privacy is our priority. All sessions and data are completely confidential and secure.
                            </p>
                        </div>

                        {/* Feature 2 */}
                        <div className="card card-hover text-center">
                            <div className="bg-gradient-to-br from-secondary-100 to-secondary-200 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6">
                                <Heart className="w-8 h-8 text-secondary-700" />
                            </div>
                            <h3 className="text-2xl font-display font-semibold text-gray-900 mb-3">
                                Empathy First
                            </h3>
                            <p className="text-gray-600">
                                Our consultants are trained to listen with care, understanding, and genuine compassion.
                            </p>
                        </div>

                        {/* Feature 3 */}
                        <div className="card card-hover text-center">
                            <div className="bg-gradient-to-br from-accent-100 to-accent-200 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6">
                                <Users className="w-8 h-8 text-accent-700" />
                            </div>
                            <h3 className="text-2xl font-display font-semibold text-gray-900 mb-3">
                                Matched for You
                            </h3>
                            <p className="text-gray-600">
                                AI-powered matching ensures you connect with the right consultant for your needs.
                            </p>
                        </div>
                    </div>

                    {/* Age Group Approach */}
                    <div className="mt-20">
                        <h3 className="text-3xl font-display font-bold text-center text-gray-900 mb-12">
                            Special Approach by Age Group
                        </h3>

                        <div className="grid md:grid-cols-3 gap-6">
                            <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-8 rounded-2xl border border-blue-200">
                                <div className="text-2xl font-bold text-blue-900 mb-3">For Young Minds</div>
                                <p className="text-blue-800">
                                    Navigating school, relationships, and early adulthood with confidence and clarity.
                                </p>
                            </div>

                            <div className="bg-gradient-to-br from-purple-50 to-purple-100 p-8 rounded-2xl border border-purple-200">
                                <div className="text-2xl font-bold text-purple-900 mb-3">For Rock Solid Hearts</div>
                                <p className="text-purple-800">
                                    Life's challenges need a safe space. Share your heart with someone who understands.
                                </p>
                            </div>

                            <div className="bg-gradient-to-br from-pink-50 to-pink-100 p-8 rounded-2xl border border-pink-200">
                                <div className="text-2xl font-bold text-pink-900 mb-3">For Softer You</div>
                                <p className="text-pink-800">
                                    Finding peace and comfort in life's later chapters. You deserve support and care.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Services Section */}
            <section id="services" className="section bg-gray-50">
                <div className="container-custom">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl md:text-5xl font-display font-bold text-gray-900 mb-4">
                            Our Services
                        </h2>
                        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
                            Comprehensive wellbeing solutions tailored to your needs
                        </p>
                    </div>

                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {/* Service Cards */}
                        {[
                            {
                                icon: MessageCircle,
                                title: 'Discovery Call',
                                duration: '30 min',
                                price: '₹499',
                                description: 'Get to know us and explore how we can support your journey',
                                color: 'primary'
                            },
                            {
                                icon: Activity,
                                title: 'Virtual Consultation',
                                duration: '1 hr',
                                price: '₹999',
                                description: 'One-on-one session with a matched wellbeing consultant',
                                color: 'secondary'
                            },
                            {
                                icon: Brain,
                                title: 'Wellness Plan',
                                duration: '1 hr',
                                price: '₹1,499',
                                description: 'Personalized wellness roadmap with actionable steps',
                                color: 'accent'
                            },
                            {
                                icon: Star,
                                title: 'Professional Coaching',
                                duration: '1 hr',
                                price: '₹4,999',
                                description: 'Advanced coaching for career and life goals',
                                color: 'primary'
                            },
                            {
                                icon: Users,
                                title: 'Family Workshop',
                                duration: '1 hr',
                                price: '₹9,999',
                                description: 'Strengthen family bonds and communication',
                                color: 'secondary'
                            },
                            {
                                icon: Calendar,
                                title: 'Corporate Session',
                                duration: '2 hr',
                                price: 'Custom',
                                description: 'Team wellbeing and stress management workshops',
                                color: 'accent'
                            },
                        ].map((service, index) => (
                            <div key={index} className="card card-hover group">
                                <div className={`bg-gradient-to-br from-${service.color}-100 to-${service.color}-200 w-14 h-14 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                                    <service.icon className={`w-7 h-7 text-${service.color}-700`} />
                                </div>

                                <h3 className="text-xl font-display font-semibold text-gray-900 mb-2">
                                    {service.title}
                                </h3>

                                <div className="flex items-center gap-4 mb-3 text-sm text-gray-600">
                                    <span className="flex items-center gap-1">
                                        <Clock className="w-4 h-4" />
                                        {service.duration}
                                    </span>
                                    <span className="font-semibold text-primary-700">{service.price}</span>
                                </div>

                                <p className="text-gray-600 mb-4">
                                    {service.description}
                                </p>

                                <button className="text-primary-700 font-medium flex items-center gap-2 group-hover:gap-3 transition-all">
                                    Book Now
                                    <ArrowRight className="w-4 h-4" />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Testimonials Section */}
            <section id="testimonials" className="section bg-white">
                <div className="container-custom">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl md:text-5xl font-display font-bold text-gray-900 mb-4">
                            What Our Clients Say
                        </h2>
                        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
                            Real stories from people who found support and growth
                        </p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-8">
                        {[
                            {
                                name: 'Priya S.',
                                role: 'Software Engineer',
                                content: 'Soul Squad helped me navigate work stress and anxiety. The consultant matched to me understood my challenges perfectly. Highly recommended!',
                                rating: 5
                            },
                            {
                                name: 'Rahul M.',
                                role: 'Entrepreneur',
                                content: 'I was skeptical at first, but the personalized approach and genuine care changed my perspective. Best decision for my emotional wellbeing.',
                                rating: 5
                            },
                            {
                                name: 'Anjali K.',
                                role: 'Teacher',
                                content: 'The family workshop brought us closer together. Our consultant created a safe space for everyone to share and heal.',
                                rating: 5
                            },
                        ].map((testimonial, index) => (
                            <div key={index} className="card card-hover">
                                <div className="flex gap-1 mb-4">
                                    {[...Array(testimonial.rating)].map((_, i) => (
                                        <Star key={i} className="w-5 h-5 text-accent-500 fill-accent-500" />
                                    ))}
                                </div>

                                <p className="text-gray-700 mb-6 italic">
                                    "{testimonial.content}"
                                </p>

                                <div className="flex items-center gap-3">
                                    <div className="w-12 h-12 bg-gradient-to-br from-primary-400 to-secondary-400 rounded-full flex items-center justify-center text-white font-semibold">
                                        {testimonial.name.charAt(0)}
                                    </div>
                                    <div>
                                        <div className="font-semibold text-gray-900">{testimonial.name}</div>
                                        <div className="text-sm text-gray-600">{testimonial.role}</div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="section bg-gradient-to-br from-primary-600 to-secondary-600 text-white">
                <div className="container-custom text-center">
                    <h2 className="text-4xl md:text-5xl font-display font-bold mb-6">
                        Ready to Start Your Wellbeing Journey?
                    </h2>
                    <p className="text-xl text-primary-100 mb-8 max-w-2xl mx-auto">
                        Join hundreds of people who have found support, growth, and peace with Soul Squad
                    </p>

                    <div className="flex flex-col sm:flex-row gap-4 justify-center">
                        <button className="btn bg-white text-primary-700 hover:bg-gray-100 text-lg">
                            Get Started Free
                            <ArrowRight className="w-5 h-5" />
                        </button>
                        <button className="btn bg-transparent border-2 border-white text-white hover:bg-white/10 text-lg">
                            Talk to a Consultant
                        </button>
                    </div>

                    <p className="text-sm text-primary-100 mt-6">
                        No credit card required • 100% confidential • Cancel anytime
                    </p>
                </div>
            </section>

            <Footer />
        </div>
    )
}
