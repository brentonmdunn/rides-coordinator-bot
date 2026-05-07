import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Send, MessageSquare } from 'lucide-react'
import { apiFetch, getApiUrl } from '../lib/api'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { PageLayout } from '../components/shared'
import { ModeToggle } from '../components/mode-toggle'

/** A single modmail message returned by the API. */
interface ModmailMessage {
    id: number
    user_id: string
    sender_type: 'user' | 'admin' | 'bot'
    sender_id: string
    sender_name: string | null
    content: string
    attachments_json: string | null
    created_at: string
}

/** A conversation summary returned by the conversations endpoint. */
interface Conversation {
    user_id: string
    last_message_content: string
    last_message_at: string | null
    sender_name: string | null
    sender_type: string
    message_count: number
    username: string | null
}

/** Derive a display name for a conversation. */
function conversationLabel(conv: Conversation): string {
    return conv.username || conv.sender_name || conv.user_id
}

/** Format an ISO timestamp for the conversation list. */
function shortTimestamp(iso: string | null): string {
    if (!iso) return ''
    const d = new Date(iso)
    const now = new Date()
    if (d.toDateString() === now.toDateString()) {
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

/** Format an ISO timestamp for inside the chat. */
function chatTimestamp(iso: string): string {
    const d = new Date(iso)
    return d.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    })
}

// ---------------------------------------------------------------------------
// Conversation list sidebar
// ---------------------------------------------------------------------------

function ConversationList({
    conversations,
    selectedUserId,
    onSelect,
}: {
    conversations: Conversation[]
    selectedUserId: string | null
    onSelect: (userId: string) => void
}) {
    if (conversations.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 dark:text-slate-500 gap-2 px-4 text-center">
                <MessageSquare className="w-10 h-10" />
                <p className="text-sm">No conversations yet</p>
                <p className="text-xs">Messages will appear here when users DM the bot.</p>
            </div>
        )
    }

    return (
        <div className="flex flex-col overflow-y-auto">
            {conversations.map((conv) => {
                const active = conv.user_id === selectedUserId
                return (
                    <button
                        key={conv.user_id}
                        onClick={() => onSelect(conv.user_id)}
                        className={`text-left px-4 py-3 border-b border-slate-100 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors ${active ? 'bg-slate-100 dark:bg-zinc-800' : ''}`}
                    >
                        <div className="flex justify-between items-baseline">
                            <span className="font-medium text-sm truncate">
                                {conversationLabel(conv)}
                            </span>
                            <span className="text-xs text-slate-400 dark:text-slate-500 ml-2 shrink-0">
                                {shortTimestamp(conv.last_message_at)}
                            </span>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">
                            {conv.last_message_content}
                        </p>
                    </button>
                )
            })}
        </div>
    )
}

// ---------------------------------------------------------------------------
// Chat messages pane
// ---------------------------------------------------------------------------

function ChatPane({
    userId,
    username,
}: {
    userId: string
    username: string | null
}) {
    const queryClient = useQueryClient()
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const [draft, setDraft] = useState('')

    const { data, isLoading } = useQuery<{ messages: ModmailMessage[] }>({
        queryKey: ['modmail-messages', userId],
        queryFn: async () => {
            const res = await apiFetch(`/api/modmail/conversations/${userId}/messages?limit=200`)
            return res.json()
        },
        refetchInterval: false,
    })

    const messages = data?.messages ?? []

    // Auto-scroll on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages.length])

    const sendMutation = useMutation({
        mutationFn: async (message: string) => {
            await apiFetch(`/api/modmail/conversations/${userId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            })
        },
        onSuccess: () => {
            setDraft('')
            queryClient.invalidateQueries({ queryKey: ['modmail-messages', userId] })
            queryClient.invalidateQueries({ queryKey: ['modmail-conversations'] })
        },
    })

    // Listen for WebSocket updates
    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const wsUrl = getApiUrl('/api/modmail/ws').replace(/^http/, 'ws')
        const fullUrl = wsUrl.startsWith('ws') ? wsUrl : `${protocol}://${window.location.host}${wsUrl}`
        const ws = new WebSocket(fullUrl)

        ws.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data)
                if (payload.type === 'new_message') {
                    queryClient.invalidateQueries({ queryKey: ['modmail-messages'] })
                    queryClient.invalidateQueries({ queryKey: ['modmail-conversations'] })
                }
            } catch {
                // ignore malformed messages
            }
        }

        return () => ws.close()
    }, [queryClient])

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        const trimmed = draft.trim()
        if (!trimmed || sendMutation.isPending) return
        sendMutation.mutate(trimmed)
    }

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="px-4 py-3 border-b border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900">
                <h2 className="font-semibold text-sm">
                    {username || userId}
                </h2>
                <p className="text-xs text-slate-400 dark:text-slate-500">
                    User ID: {userId}
                </p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
                {isLoading && (
                    <p className="text-center text-sm text-slate-400">Loading messages...</p>
                )}
                {messages.map((msg) => {
                    const isUser = msg.sender_type === 'user'
                    return (
                        <div
                            key={msg.id}
                            className={`flex ${isUser ? 'justify-start' : 'justify-end'}`}
                        >
                            <div
                                className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                                    isUser
                                        ? 'bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-slate-100'
                                        : 'bg-blue-600 text-white'
                                }`}
                            >
                                {!isUser && msg.sender_name && (
                                    <p className="text-xs font-medium mb-0.5 opacity-80">
                                        {msg.sender_name}
                                    </p>
                                )}
                                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                                <p
                                    className={`text-[10px] mt-1 ${
                                        isUser
                                            ? 'text-slate-400 dark:text-slate-500'
                                            : 'text-blue-200'
                                    }`}
                                >
                                    {chatTimestamp(msg.created_at)}
                                </p>
                            </div>
                        </div>
                    )
                })}
                <div ref={messagesEndRef} />
            </div>

            {/* Compose bar */}
            <form
                onSubmit={handleSubmit}
                className="px-4 py-3 border-t border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 flex gap-2"
            >
                <Input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder="Type a message..."
                    className="flex-1"
                    disabled={sendMutation.isPending}
                />
                <Button
                    type="submit"
                    size="icon"
                    disabled={!draft.trim() || sendMutation.isPending}
                >
                    <Send className="w-4 h-4" />
                </Button>
            </form>

            {sendMutation.isError && (
                <p className="px-4 py-1 text-xs text-red-500">
                    Failed to send. Please try again.
                </p>
            )}
        </div>
    )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function Modmail() {
    const [selectedUserId, setSelectedUserId] = useState<string | null>(null)

    const { data } = useQuery<{ conversations: Conversation[] }>({
        queryKey: ['modmail-conversations'],
        queryFn: async () => {
            const res = await apiFetch('/api/modmail/conversations')
            return res.json()
        },
    })

    const conversations = data?.conversations ?? []

    const selectedConversation = conversations.find((c) => c.user_id === selectedUserId)

    const handleSelect = useCallback((userId: string) => {
        setSelectedUserId(userId)
    }, [])

    return (
        <PageLayout
            header={
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <Link
                            to="/"
                            className="inline-flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                        >
                            <ArrowLeft className="w-4 h-4" />
                            Dashboard
                        </Link>
                        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
                            Modmail
                        </h1>
                    </div>
                    <ModeToggle />
                </div>
            }
        >
            <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-lg overflow-hidden flex" style={{ height: 'calc(100vh - 180px)', minHeight: '500px' }}>
                {/* Sidebar */}
                <div className="w-72 shrink-0 border-r border-slate-200 dark:border-zinc-700 flex flex-col">
                    <div className="px-4 py-3 border-b border-slate-200 dark:border-zinc-700">
                        <h3 className="font-semibold text-sm text-slate-700 dark:text-slate-200">
                            Conversations
                        </h3>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        <ConversationList
                            conversations={conversations}
                            selectedUserId={selectedUserId}
                            onSelect={handleSelect}
                        />
                    </div>
                </div>

                {/* Chat area */}
                <div className="flex-1 flex flex-col">
                    {selectedUserId ? (
                        <ChatPane
                            key={selectedUserId}
                            userId={selectedUserId}
                            username={selectedConversation?.username ?? null}
                        />
                    ) : (
                        <div className="flex-1 flex items-center justify-center text-slate-400 dark:text-slate-500">
                            <div className="text-center">
                                <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p className="text-sm">Select a conversation to start chatting</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </PageLayout>
    )
}

export default Modmail
