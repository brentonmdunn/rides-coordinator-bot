import type { HousingGroup } from '../types'
import { Card } from './ui/card'
import { Button } from './ui/button'
import { Copy, Check } from 'lucide-react'
import { cn } from '../lib/utils'

interface PickupGroupProps {
    groupName: string
    groupData: HousingGroup
    copiedUsername: string | null
    onCopy: (text: string) => void
}

function PickupGroup({ groupName, groupData, copiedUsername, onCopy }: PickupGroupProps) {
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
                    
                    const isCopied = copiedUsername === copySummary;

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
                                    className={cn(
                                        "h-7 px-2 text-xs gap-1.5 transition-all text-muted-foreground hover:text-foreground",
                                        isCopied && "text-success border-success/50 bg-success/5 hover:text-success"
                                    )}
                                    title="Copy usernames for tagging"
                                >
                                    {isCopied ? (
                                        <>
                                            <Check className="h-3.5 w-3.5" />
                                            <span>Copied</span>
                                        </>
                                    ) : (
                                        <>
                                            <Copy className="h-3.5 w-3.5" />
                                            <span>Copy Tags</span>
                                        </>
                                    )}
                                </Button>
                            </div>
                            <div className="text-muted-foreground ml-4">
                                {people.map((person, idx) => (
                                    <span key={idx}>
                                        {person.discord_username ? (
                                            <button
                                                onClick={() => onCopy("@" + person.discord_username!)}
                                                className={`hover:text-info hover:underline cursor-pointer transition-colors break-all text-left ${copiedUsername === "@" + person.discord_username
                                                    ? 'text-success font-medium'
                                                    : ''
                                                    }`}
                                                title={`Click to copy @${person.discord_username}`}
                                                aria-label={`Copy @${person.discord_username} to clipboard`}
                                            >
                                                {person.name}
                                                {copiedUsername === "@" + person.discord_username && ' ✓'}
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
