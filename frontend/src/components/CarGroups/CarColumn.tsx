import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import type { CarGroup, Rider } from './types';
import RiderCard from './RiderCard';

interface CarColumnProps {
    car: CarGroup;
    onRemoveCar?: (id: string) => void;
}

function parseTimeToMinutes(t: string): number {
    if (!t) return 0;
    const clean = t.trim().toLowerCase();
    // try to match basic patterns (e.g. 5:30 pm, 17:30, 4:00:00 PM)
    let hours = 0;
    let minutes = 0;
    const match = clean.match(/(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm)?/);
    if (match) {
        hours = parseInt(match[1], 10);
        minutes = match[2] ? parseInt(match[2], 10) : 0;
        const meridian = match[3];
        if (meridian === 'pm' && hours < 12) hours += 12;
        if (meridian === 'am' && hours === 12) hours = 0;
    }
    return hours * 60 + minutes;
}

export default function CarColumn({ car, onRemoveCar }: CarColumnProps) {
    const { setNodeRef, isOver } = useDroppable({
        id: car.id,
    });

    const isFull = car.riders.length >= 4; // Typical capacity, can make soft warning

    // Calculate Max departure time
    let maxTimeStr = 'None';
    let maxMinutes = -1;
    let locations = new Set<string>();

    car.riders.forEach(r => {
        const m = parseTimeToMinutes(r.earliestLeaveTime);
        if (m > maxMinutes) {
            maxMinutes = m;
            maxTimeStr = r.earliestLeaveTime || 'Unknown';
        }
        if (r.pickupLocation) {
            locations.add(r.pickupLocation);
        }
    });

    const hasMixedLocations = locations.size > 1;

    return (
        <div 
            className={`
                bg-slate-50 dark:bg-zinc-950 p-4 rounded-xl border-2 flex flex-col min-h-[250px]
                ${isOver ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/10' : 'border-slate-200 dark:border-zinc-800'}
            `}
        >
            <div className="flex justify-between items-center mb-3">
                <h3 className="font-bold text-lg">🚗 Car ({car.riders.length})</h3>
                {onRemoveCar && (
                    <button 
                        onClick={() => onRemoveCar(car.id)}
                        className="text-slate-400 hover:text-red-500 text-sm p-1"
                        title="Delete Car (moves riders back to pool)"
                    >
                        ✕
                    </button>
                )}
            </div>
            
            <div className="mb-4 space-y-2 text-sm">
                <div className="flex justify-between">
                    <span className="text-slate-500">Leave Time:</span>
                    <span className="font-mono font-bold bg-slate-200 dark:bg-zinc-800 px-2 rounded">
                        {maxTimeStr}
                    </span>
                </div>
                
                {hasMixedLocations && (
                    <div className="text-xs bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400 p-2 rounded flex flex-col gap-1">
                        <strong>⚠️ Multi-stop warning</strong>
                        <span>{Array.from(locations).join(', ')}</span>
                    </div>
                )}
                
                {isFull && (
                    <div className="text-xs bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 p-2 rounded">
                        <strong>⚠️ Capacity Warning:</strong> This car has 4+ people.
                    </div>
                )}
            </div>

            <div 
                ref={setNodeRef}
                className="flex-1 rounded-lg border-2 border-dashed border-slate-200 dark:border-zinc-800 p-2"
            >
                <SortableContext 
                    id={car.id}
                    items={car.riders.map(r => r.id)} 
                    strategy={verticalListSortingStrategy}
                >
                    {car.riders.map(rider => (
                        <RiderCard key={rider.id} rider={rider} />
                    ))}
                </SortableContext>
                
                {car.riders.length === 0 && (
                    <div className="h-full flex items-center justify-center text-slate-400 text-sm italic py-8">
                        Drop riders here
                    </div>
                )}
            </div>
        </div>
    );
}
