import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { ModeToggle } from '../components/mode-toggle'
import EnvironmentBanner from '../components/EnvironmentBanner'

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
            {/* Introduction */}
            <section className="mb-12">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                Introduction
              </h2>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
                Welcome to Ridebot! This guide will walk you through everything you need to know
                to coordinate rides efficiently.
              </p>
              {/* Add your content here */}
            </section>

            {/* Getting Started */}
            <section className="mb-12">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                Getting Started
              </h2>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
                {/* Add your content here */}
              </p>
            </section>

            {/* Add more sections as needed */}
            <section className="mb-12">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                Requesting a Ride
              </h2>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
                {/* Add your content here */}
              </p>
            </section>

            <section className="mb-12">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                For Drivers
              </h2>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
                {/* Add your content here */}
              </p>
            </section>

            <section className="mb-12">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                Frequently Asked Questions
              </h2>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
                {/* Add your content here */}
              </p>
            </section>
          </article>
        </div>
      </div>
    </>
  )
}

export default Learn
