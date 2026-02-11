import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { ModeToggle } from '../components/mode-toggle'
import EnvironmentBanner from '../components/EnvironmentBanner'
import { TutorialSection, TutorialSubheader, TutorialText, TutorialList, TutorialTable } from '../components/TutorialComponents'

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
                                Yay thanks for being a ride coordinator! This guide will walk you through everything you need to know
                                to coordinate rides efficiently.
                            </TutorialText>

                            <TutorialSubheader>What does a ride coordinator do?</TutorialSubheader>
                            <TutorialText>
                                Ride coordinators are responsible for organizing rides to Friday Fellowship and Sunday Service (and all class if it is happening on Sunday).
                                They can help other events if they want to, but it is not required. <b>Your primary goal is to make sure everyone who needs a ride can get one.
                                    Your secondary goal is to minimize the amount of drivers and the amount of time that drivers spend driving.</b> Campus is large, and a good route
                                can make the difference between a 5 minute drive and a 20 minute drive.
                            </TutorialText>

                            <TutorialSubheader>What do I need to know?</TutorialSubheader>
                            <TutorialText>
                                Not much! For most of the annoying tasks, the bot will handle it. You will need a basic understanding of the area around campus and where each
                                college is located on campus (list of pickup locations <a href="https://maps.app.goo.gl/7hoW2ZkAJAVaqVWH8">here</a>). For the forseeable future,
                                Brenton will maintain the ridebot codebase for the foreseeable future, so you will not need to know any programming and can just yell at him if something breaks.
                                A lot of the week to week work is making sure that you have enough drivers.
                            </TutorialText>
                        </TutorialSection>

                        <TutorialSection title="Week to Week Responsibilities">
                            <TutorialText>
                                As ride coordinator, you should have been added to <code>#driver-chat-wooooo</code> and <code>#driver-bot-spam</code>. You should also have write acess to <code>#rides-announcements</code>.
                            </TutorialText>

                            <TutorialText>
                                Here is what a normal week looks like for a ride coordinator:
                            </TutorialText>
                            <TutorialList>
                                <li>Ridebot will post a message in <code>#rides-announcements</code> on Wednesday noon asking for who needs a ride.</li>
                                <li>Around this time, you should use <code>/ask-drivers</code> in <code>#driver-chat-wooooo</code> to ask for drivers.</li>
                                <li>For Friday Fellowship, create ride groups and send them out in <code>#rides-announcements</code> around Friday noon.</li>
                                <li>For Sunday Service (and class if applicable), create ride groups and send them out in <code>#rides-announcements</code> around Saturday evening.</li>
                            </TutorialList>

                            <TutorialText>
                                Note: Finding drivers will be the most difficult part of this job. Feel free to text Clarence or the YAs for help.
                            </TutorialText>

                            <TutorialText>
                                Another note: People will forget to sign up and ask you last minute. This is inevitable but just do your best to slot them in somewhere. You can crash out to Sydney
                                or Brenton LOL.
                            </TutorialText>
                        </TutorialSection>

                        <TutorialSection title="Creating Ride Routes">
                            <TutorialText>
                                The goal of creating ride routes is to minimize the amount of time drivers spend driving. This means grouping rides by location and creating routes that are as short
                                as possible. It takes about 20 minutes to drive to church or Clanence's. Most drivers live between campus and UTC. Try to fill up cars as much as possible in order
                                to minimize the amount of drivers. However, if a drive is more than like 10-ish minutes, it is better to have two drivers.
                            </TutorialText>
                            <TutorialText>
                                We typically group rides into certain zones. These zones are:
                            </TutorialText>
                            <TutorialList>
                                <li>Scholars Drive (Eighth, Revelle, Muir, Sixth, Marshall, ERC, Seventh)</li>
                                <li>East Campus (Pepper Canyon and Warren)</li>
                                <li>Rita</li>
                                <li>Off campus</li>
                            </TutorialList>
                            <TutorialSubheader>Scholars Drive</TutorialSubheader>
                            <TutorialText>
                                Most people who live on campus live on Scholars Drive. Most drivers come from the south of campus (Eighth) and head north, so when creating routes, the southernmost
                                pickup should be first (i.e., Eighth then Muir and not the other way around). While keeping pickups close together is good, since drivers already need to go from
                                Eighth to Seventh to get to church/Clarence's, having a pickup at Eighth and Seventh isn't the worst thing in the world. If needed, Marshall can be picked up at
                                Geisel Loop and be classified in the east campus zone, although this is not preferred since Geisel Loop is annoying to drive to.
                            </TutorialText>
                            <TutorialSubheader>East Campus</TutorialSubheader>
                            <TutorialText>
                                This includes Pepper Canyon and Warren (and sometimes Marshall at Geisel Loop). The pickup spot for both Pepper Canyon East and West is Innovation Lane. The Warren
                                spot is Equality Lane since it is easiser to get in and out of compared to Justice Lane.
                            </TutorialText>
                            <TutorialSubheader>Rita</TutorialSubheader>
                            <TutorialText>
                                From a driver perspective, Rita is really annoying to drive to. Try to keep this separate from other zones, although can be grouped with others if necessary.
                            </TutorialText>
                            <TutorialSubheader>Off Campus</TutorialSubheader>
                            <TutorialText>
                                This includes all off campus locations. Generally, it is difficult to group off campus with campus. For off campus, don't dox people's apartments or addresses and
                                just DM the pickup location to both them and their driver.
                            </TutorialText>
                        </TutorialSection>

                        <TutorialSection title="How to Use RideBot">
                            <TutorialText>
                                The main way to interact with RideBot is through this website. All widgets on the main page contain an info button ⓘ that will show you more information about the widget.
                            </TutorialText>

                            <TutorialTable
                                headers={['Widget', 'Description']}
                                rows={[
                                    ['Ask Rides Status Dashboard', 'Overview of whether rides request was sent out and reaction summary'],
                                    ['Ask Rides Reactions', 'Names of people who reacted for a ride'],
                                    ['Driver Reactions', 'Names of drivers who reacted to give a ride'],
                                    ['List Pickups', 'Pickup locations of people who reacted for a ride'],
                                    ['Group Rides', 'Automatically groups rides and creates routes (does not always work but is a good starting place)'],
                                    ['Route Builder', 'Manually create routes'],
                                    ['Feature Flags', 'Toggle features on and off (only modify if you know what you are doing)'],
                                ]}
                            />
                        </TutorialSection>
                        <TutorialText>
                            Other miscellaneous things to know:
                            <TutorialList>
                                <li>If someone's Discord username is not on the spreadsheet and they react for a ride, a new channel will automatically be created for them and RideBot will ask where they live.</li>
                                <li>For drivers, if they react and their Discord username is not on the spreadsheet, instead of their name popping up, it will be their username.</li>
                                <li>Changes made to the spreadsheet may take up to 24 hours to be reflected in RideBot (though usually a lot faster).</li>
                            </TutorialList>
                        </TutorialText>
                    </article>
                </div>
            </div>
        </>
    )

}

export default Learn

