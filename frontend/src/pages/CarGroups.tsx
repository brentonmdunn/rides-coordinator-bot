import CarGroupsBoard from '../components/CarGroups/CarGroupsBoard';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export default function CarGroups() {
    return (
        <div className="min-h-screen w-full bg-gray-50 dark:bg-zinc-950 py-12 px-4 font-sans text-slate-900 dark:text-slate-100 transition-colors duration-300">
            <div className="max-w-7xl mx-auto mb-8">
                <Link to="/" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors font-medium mb-4">
                    <ArrowLeft className="w-4 h-4" />
                    Back to Admin Dashboard
                </Link>
                <div className="flex flex-col gap-2">
                    <h1 className="text-4xl font-extrabold tracking-tight">Car Groups Builder</h1>
                    <p className="text-lg text-slate-600 dark:text-slate-400">
                        Drag and drop members into cars to organize rides based on availability and location.
                    </p>
                </div>
            </div>

            <CarGroupsBoard />
        </div>
    );
}
