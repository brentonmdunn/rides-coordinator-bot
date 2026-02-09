import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { ModeToggle } from '../components/mode-toggle'
import EnvironmentBanner from '../components/EnvironmentBanner'
import { TutorialSection, TutorialSubheader, TutorialText } from '../components/TutorialComponents'

function Learn() {
    return (
        <>
            <EnvironmentBanner />
            <div className="min-h-screen w-full max-w-[100vw] overflow-x-hidden bg-gray-50 dark:bg-zinc-950 py-12 px-4 font-sans text-slate-900 dark:text-slate-100 transition-colors duration-300">
                <div className="max-w-4xl mx-auto">
                    {/* Header */}
                    <header className="flex flex-col md:flex-row md:items-start md:justify-between gap-6 mb-12">
                        <div className="flex-1">
                            <Link
                                to="/"
                                className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors mb-4"
                            >
                                <ArrowLeft className="w-4 h-4" />
                                Back to Dashboard
                            </Link>
                            <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-5xl mb-4">
                                📚 How to Use Ridebot
                            </h1>
                            <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl">
                                A complete guide to coordinating rides with Ridebot.
                            </p>
                        </div>
                        <div className="flex justify-center md:justify-end">
                            <ModeToggle />
                        </div>
                    </header>

                    {/* Tutorial Content */}
                    <article className="prose prose-slate dark:prose-invert max-w-none">
                        <TutorialSection title="Introduction">
                            <TutorialText>
                                Welcome to Ridebot! This guide will walk you through everything you need to know
                                to coordinate rides efficiently.

                            </TutorialText>
                        </TutorialSection>

                        <TutorialSection title="Getting Started">
                            <TutorialText>
                                First, you'll need to join the Discord server and react to a ride announcement.
                            </TutorialText>

                            <TutorialSubheader>Joining the Server</TutorialSubheader>
                            <TutorialText>
                                Ask a friend for an invite link to join the Discord server.
                            </TutorialText>

                            <TutorialSubheader>Finding Ride Announcements</TutorialSubheader>
                            <TutorialText>
                                Look for ride announcement posts in the rides channel.
                            </TutorialText>
                        </TutorialSection>

                        <TutorialSection title="Requesting a Ride">
                            <TutorialText>
                                {/* Add your content here */}
                            </TutorialText>
                        </TutorialSection>

                        <TutorialSection title="For Drivers">
                            <TutorialText>
                                {/* Add your content here */}
                            </TutorialText>
                        </TutorialSection>

                        <TutorialSection title="Frequently Asked Questions">
                            <TutorialText>
                                {/* Add your content here */}
                            </TutorialText>
                        </TutorialSection>
                    </article>
                </div>
            </div>
        </>
    )
}

export default Learn

