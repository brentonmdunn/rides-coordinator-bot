import type { HousingGroup } from '../types'
import { Card } from './ui/card'
import { Button } from './ui/button'
import { Copy } from 'lucide-react'

interface PickupGroupProps {
    groupName: string
    groupData: HousingGroup
    onCopy: (text: string) => void
}

function PickupGroup({ groupName, groupData, onCopy }: PickupGroupProps) {
    return (
        <Card className="rounded-lg overflow-hidden border border-border shadow-none">
            {/* Group Header */}
            <div className="bg-muted px-4 py-3 border-b border-border">
                <h4 className="font-semibold text-foreground flex items-center gap-2 m-0 text-base">
                    <span>{groupData.emoji}</span>
                    <span className="capitalize">{groupName}</span>
                    <span className="text-sm font-normal text-muted-foreground">
                        ({groupData.count} {groupData.count === 1 ? 'person' : 'people'})
                    </span>
                </h4>
            </div>

            {/* Locations within this group */}
            <div className="divide-y divide-border">
                {Object.entries(groupData.locations).map(([locationName, people]) => {
                    const getTag = (p: { name: string, discord_username: string | null }) =>
                        p.discord_username ? `@${p.discord_username}` : p.name;

                    const copySummary = people.map(p => getTag(p)).join(' ');

                    return (
                        <div key={locationName} className="p-4 bg-card">
                            <div className="capitalize font-medium text-foreground mb-2 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span>{locationName}:</span>
                                    <span className="text-xs font-normal px-2 py-0.5 bg-muted text-muted-foreground rounded-full border border-border">
                                        {people.length}
                                    </span>
                                </div>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={people.length === 0}
                                    onClick={() => onCopy(copySummary)}
                                    className="h-7 px-2 text-xs gap-1.5 transition-all text-muted-foreground hover:text-foreground"
                                    title="Copy usernames for tagging"
                                >
                                    <Copy className="h-3.5 w-3.5" />
                                    <span>Copy Tags</span>
                                </Button>
                            </div>
                            <div className="text-muted-foreground ml-4">
                                {people.map((person, idx) => (
                                    <span key={idx}>
                                        {person.discord_username ? (
                                            <button
                                                onClick={() => onCopy("@" + person.discord_username!)}
                                                className="hover:text-info hover:underline cursor-pointer transition-colors break-all text-left"
                                                title={`Click to copy @${person.discord_username}`}
                                                aria-label={`Copy @${person.discord_username} to clipboard`}
                                            >
                                                {person.name}
                                            </button>
                                        ) : (
                                            <span>{person.name}</span>
                                        )}
                                        {idx < people.length - 1 ? ', ' : ''}
                                    </span>
                                ))}
                                {people.length === 0 && (
                                    <span className="italic text-muted-foreground">No one</span>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </Card>
    )
}

export default PickupGroup
