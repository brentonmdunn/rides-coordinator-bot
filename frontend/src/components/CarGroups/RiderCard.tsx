import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { Rider } from './types';

// Simple function to assign a color based on location text
const getLocationColor = (location: string) => {
    const norm = location.toLowerCase();
    if (norm.includes('warren')) return 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300';
    if (norm.includes('erc')) return 'border-red-500 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300';
    if (norm.includes('muir')) return 'border-green-500 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300';
    if (norm.includes('marshall') || norm.includes('tmarshall')) return 'border-orange-500 bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-300';
    if (norm.includes('sixth')) return 'border-purple-500 bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300';
    if (norm.includes('seventh')) return 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-300';
    if (norm.includes('eighth')) return 'border-pink-500 bg-pink-50 dark:bg-pink-900/20 text-pink-700 dark:text-pink-300';
    if (norm.includes('revelle')) return 'border-teal-500 bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300';
    if (norm.includes('pepper')) return 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300';
    return 'border-gray-500 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300';
};

interface RiderCardProps {
    rider: Rider;
}

export default function RiderCard({ rider }: RiderCardProps) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: rider.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
    };

    const locationStyle = getLocationColor(rider.pickupLocation);

    return (
        <div
            ref={setNodeRef}
            style={style}
            {...attributes}
            {...listeners}
            className={`
                p-3 mb-2 rounded-lg border shadow-sm flex flex-col gap-2 cursor-grab active:cursor-grabbing bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-800
                ${isDragging ? 'opacity-50 ring-2 ring-blue-500 z-50' : ''}
            `}
        >
            <div className="flex justify-between items-start">
                <span className="font-semibold text-sm truncate pr-2" title={rider.discordUsername}>
                    {rider.name ? `${rider.name} (${rider.discordUsername})` : rider.discordUsername}
                </span>
                <span className="text-xs font-mono bg-slate-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-slate-600 dark:text-slate-400 whitespace-nowrap">
                    🕒 {rider.earliestLeaveTime || 'Any'}
                </span>
            </div>
            
            <div className="flex items-center">
                <span className={`text-xs px-2 py-0.5 rounded-full border ${locationStyle}`}>
                    📍 {rider.pickupLocation || 'Unknown'}
                </span>
            </div>
        </div>
    );
}
