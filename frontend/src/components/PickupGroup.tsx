import type { HousingGroup } from '../types'
import { Card } from './ui/card'

interface PickupGroupProps {
    groupName: string
    groupData: HousingGroup
    copiedUsername: string | null
    onCopy: (username: string) => void
}

function PickupGroup({ groupName, groupData, copiedUsername, onCopy }: PickupGroupProps) {
    return (
        <Card className="rounded-lg overflow-hidden border border-slate-200 dark:border-zinc-700 shadow-none">
            {/* Group Header */}
            <div className="bg-slate-100 dark:bg-zinc-800 px-4 py-3 border-b border-slate-200 dark:border-zinc-700">
                <h4 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2 m-0 text-base">
                    <span>{groupData.emoji}</span>
                    <span className="capitalize">{groupName}</span>
                    <span className="text-sm font-normal text-slate-600 dark:text-slate-400">
                        ({groupData.count} {groupData.count === 1 ? 'person' : 'people'})
                    </span>
                </h4>
            </div>

            {/* Locations within this group */}
            <div className="divide-y divide-slate-200 dark:divide-zinc-700">
                {Object.entries(groupData.locations).map(([locationName, people]) => (
                    <div key={locationName} className="p-4 bg-white dark:bg-zinc-900">
                        <div className="capitalize font-medium text-slate-800 dark:text-slate-200 mb-2 flex items-center gap-2">
                            <span>{locationName}:</span>
                            <span className="text-xs font-normal px-2 py-0.5 bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-slate-400 rounded-full border border-slate-200 dark:border-zinc-700">
                                {people.length}
                            </span>
                        </div>
                        <div className="text-slate-600 dark:text-slate-400 ml-4">
                            {people.map((person, idx) => (
                                <span key={idx}>
                                    {person.discord_username ? (
                                        <button
                                            onClick={() => onCopy(person.discord_username!)}
                                            className={`hover:text-blue-600 dark:hover:text-blue-400 hover:underline cursor-pointer transition-colors break-all text-left ${copiedUsername === person.discord_username
                                                ? 'text-green-600 dark:text-green-400 font-medium'
                                                : ''
                                                }`}
                                            title={`Click to copy @${person.discord_username}`}
                                        >
                                            {person.name}
                                            {copiedUsername === person.discord_username && ' ✓'}
                                        </button>
                                    ) : (
                                        <span>{person.name}</span>
                                    )}
                                    {idx < people.length - 1 ? ', ' : ''}
                                </span>
                            ))}
                            {people.length === 0 && (
                                <span className="italic text-slate-400 dark:text-slate-500">No one</span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </Card>
    )
}

export default PickupGroup
