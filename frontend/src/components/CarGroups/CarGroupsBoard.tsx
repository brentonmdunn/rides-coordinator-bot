import { useState } from 'react';
import { 
    DndContext, 
    DragOverlay, 
    closestCorners, 
    KeyboardSensor, 
    PointerSensor, 
    useSensor, 
    useSensors, 
    defaultDropAnimationSideEffects
} from '@dnd-kit/core';
import type {
    DragStartEvent, 
    DragOverEvent, 
    DragEndEvent
} from '@dnd-kit/core';
import { 
    arrayMove, 
    SortableContext, 
    sortableKeyboardCoordinates, 
    verticalListSortingStrategy 
} from '@dnd-kit/sortable';
import type { Rider, CarGroup } from './types';
import DataInput from './DataInput';
import RiderCard from './RiderCard';
import CarColumn from './CarColumn';
import { useDroppable } from '@dnd-kit/core';

function UnassignedPool({ riders }: { riders: Rider[] }) {
    const { setNodeRef } = useDroppable({ id: 'unassigned' });

    // Group riders by location for better scanning
    const grouped = riders.reduce((acc, rider) => {
        const loc = rider.pickupLocation || 'Unknown';
        if (!acc[loc]) acc[loc] = [];
        acc[loc].push(rider);
        return acc;
    }, {} as Record<string, Rider[]>);

    return (
        <div className="bg-slate-100 dark:bg-zinc-900/50 rounded-xl p-4 flex flex-col h-[calc(100vh-200px)] border border-slate-200 dark:border-zinc-800">
            <h2 className="text-xl font-bold mb-4 flex items-center justify-between">
                <span>Unassigned Pool</span>
                <span className="bg-slate-200 dark:bg-zinc-800 px-2 py-0.5 rounded-full text-sm">
                    {riders.length}
                </span>
            </h2>
            
            <div 
                ref={setNodeRef}
                className="flex-1 overflow-y-auto pr-2 space-y-4 pb-20"
            >
                <SortableContext 
                    id="unassigned"
                    items={riders.map(r => r.id)} 
                    strategy={verticalListSortingStrategy}
                >
                    {Object.keys(grouped).length === 0 ? (
                        <div className="text-center text-slate-500 py-10 italic">
                            No unassigned riders. Paste data above to get started.
                        </div>
                    ) : (
                        Object.entries(grouped).sort().map(([loc, ridersInLoc]) => (
                            <div key={loc} className="mb-4">
                                <h3 className="text-sm font-semibold text-slate-500 mb-2 sticky top-0 bg-slate-100 dark:bg-zinc-900/50 py-1 z-10">
                                    📍 {loc} ({ridersInLoc.length})
                                </h3>
                                <div className="space-y-2">
                                    {ridersInLoc.map(rider => (
                                        <RiderCard key={rider.id} rider={rider} />
                                    ))}
                                </div>
                            </div>
                        ))
                    )}
                </SortableContext>
            </div>
        </div>
    );
}

export default function CarGroupsBoard() {
    const [unassigned, setUnassigned] = useState<Rider[]>([]);
    const [cars, setCars] = useState<CarGroup[]>([]);
    const [activeRider, setActiveRider] = useState<Rider | null>(null);

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const handleDataParsed = (newRiders: Rider[]) => {
        setUnassigned(prev => [...prev, ...newRiders]);
    };

    const addCar = () => {
        setCars(prev => [
            ...prev,
            { id: `car-${Date.now()}`, riders: [] }
        ]);
    };

    const removeCar = (carId: string) => {
        // Move riders back to unassigned pool
        const car = cars.find(c => c.id === carId);
        if (car && car.riders.length > 0) {
            setUnassigned(prev => [...prev, ...car.riders]);
        }
        setCars(prev => prev.filter(c => c.id !== carId));
    };

    // Find which container a rider belongs to ('unassigned' or a car 'id')
    const findContainer = (id: string) => {
        if (unassigned.find(r => r.id === id)) return 'unassigned';
        const car = cars.find(c => c.riders.find(r => r.id === id));
        if (car) return car.id;
        return null;
    };

    const handleDragStart = (event: DragStartEvent) => {
        const { active } = event;
        const id = active.id as string;
        
        let rider = unassigned.find(r => r.id === id);
        if (!rider) {
            for (const car of cars) {
                const found = car.riders.find(r => r.id === id);
                if (found) {
                    rider = found;
                    break;
                }
            }
        }
        setActiveRider(rider || null);
    };

    const handleDragOver = (event: DragOverEvent) => {
        const { active, over } = event;
        if (!over) return;

        const activeId = active.id as string;
        const overId = over.id as string;

        // Determine containers
        const activeContainer = findContainer(activeId);
        // Over can be a rider card or a droppable container
        const overContainer = findContainer(overId) || (overId === 'unassigned' ? 'unassigned' : cars.find(c => c.id === overId)?.id);

        if (!activeContainer || !overContainer || activeContainer === overContainer) {
            return;
        }

        // We are moving between containers! Move item over.
        setItemsAcrossContainers(activeContainer, overContainer, activeId, overId);
    };

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;
        setActiveRider(null);

        if (!over) return;

        const activeId = active.id as string;
        const overId = over.id as string;

        const activeContainer = findContainer(activeId);
        const overContainer = findContainer(overId) || (overId === 'unassigned' ? 'unassigned' : cars.find(c => c.id === overId)?.id);

        if (!activeContainer || !overContainer) return;

        if (activeContainer === overContainer) {
            // Reordering within the same container
            if (activeId !== overId) {
                if (activeContainer === 'unassigned') {
                    setUnassigned(items => {
                        const oldIndex = items.findIndex(i => i.id === activeId);
                        const newIndex = items.findIndex(i => i.id === overId);
                        return arrayMove(items, oldIndex, newIndex);
                    });
                } else {
                    setCars(prevCars => {
                        return prevCars.map(car => {
                            if (car.id === activeContainer) {
                                const oldIndex = car.riders.findIndex(i => i.id === activeId);
                                const newIndex = car.riders.findIndex(i => i.id === overId);
                                return { ...car, riders: arrayMove(car.riders, oldIndex, newIndex) };
                            }
                            return car;
                        });
                    });
                }
            }
        }
    };

    const setItemsAcrossContainers = (activeContainer: string, overContainer: string, activeId: string, overId: string) => {
        // Find item
        let item: Rider;
        if (activeContainer === 'unassigned') {
            item = unassigned.find(r => r.id === activeId)!;
        } else {
            item = cars.find(c => c.id === activeContainer)!.riders.find(r => r.id === activeId)!;
        }

        // Remove from active container
        if (activeContainer === 'unassigned') {
            setUnassigned(prev => prev.filter(r => r.id !== activeId));
        } else {
            setCars(prev => prev.map(c => c.id === activeContainer ? { ...c, riders: c.riders.filter(r => r.id !== activeId) } : c));
        }

        // Add to over container at the correct index
        if (overContainer === 'unassigned') {
            setUnassigned(prev => {
                const newIndex = overId === 'unassigned' ? prev.length : prev.findIndex(r => r.id === overId);
                const safeIndex = newIndex >= 0 ? newIndex : prev.length;
                const newArr = [...prev];
                newArr.splice(safeIndex, 0, item);
                return newArr;
            });
        } else {
            setCars(prev => prev.map(c => {
                if (c.id === overContainer) {
                    const newIndex = overId === overContainer ? c.riders.length : c.riders.findIndex(r => r.id === overId);
                    const safeIndex = newIndex >= 0 ? newIndex : c.riders.length;
                    const newArr = [...c.riders];
                    newArr.splice(safeIndex, 0, item);
                    return { ...c, riders: newArr };
                }
                return c;
            }));
        }
    };

    const dropAnimation = {
        sideEffects: defaultDropAnimationSideEffects({ styles: { active: { opacity: '0.4' } } }),
    };

    return (
        <div className="max-w-7xl mx-auto space-y-6">
            <DataInput onDataParsed={handleDataParsed} />

            <DndContext 
                sensors={sensors}
                collisionDetection={closestCorners}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDragEnd={handleDragEnd}
            >
                <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
                    
                    {/* Left Column: Pool */}
                    <div className="md:col-span-1">
                        <UnassignedPool riders={unassigned} />
                    </div>

                    {/* Right Columns: Cars */}
                    <div className="md:col-span-3">
                        <div className="flex justify-between items-center mb-6 border-b border-slate-200 dark:border-zinc-800 pb-4">
                            <h2 className="text-2xl font-bold">Planned Cars</h2>
                            <button
                                onClick={addCar}
                                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium shadow transition-colors"
                            >
                                + Add Empty Car
                            </button>
                        </div>

                        {cars.length === 0 ? (
                            <div className="flex flex-col items-center justify-center p-12 bg-slate-50 dark:bg-zinc-900/50 rounded-xl border-2 border-dashed border-slate-200 dark:border-zinc-800 text-slate-500">
                                <p className="mb-4 text-lg">No cars created yet.</p>
                                <button
                                    onClick={addCar}
                                    className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-md font-medium shadow transition-colors block mx-auto"
                                >
                                    + Add Your First Car
                                </button>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 auto-rows-max">
                                {cars.map(car => (
                                    <CarColumn key={car.id} car={car} onRemoveCar={removeCar} />
                                ))}
                            </div>
                        )}
                    </div>

                </div>

                <DragOverlay dropAnimation={dropAnimation}>
                    {activeRider ? <RiderCard rider={activeRider} /> : null}
                </DragOverlay>
            </DndContext>
        </div>
    );
}
