import { useState } from 'react';
import Papa from 'papaparse';
import type { Rider } from './types';

interface DataInputProps {
    onDataParsed: (riders: Rider[]) => void;
}

export default function DataInput({ onDataParsed }: DataInputProps) {
    const [csvText, setCsvText] = useState('');
    const [error, setError] = useState<string | null>(null);

    const handleParse = () => {
        setError(null);
        Papa.parse(csvText, {
            header: true,
            skipEmptyLines: true,
            complete: (results) => {
                const parsedRiders: Rider[] = [];
                for (const row of results.data as any[]) {
                    // Try to match headers loosely (case-insensitive, trimming)
                    const normalizedRow: Record<string, string> = {};
                    for (const key in row) {
                        normalizedRow[key.trim().toLowerCase()] = row[key]?.trim() || '';
                    }

                    const discordUsername = normalizedRow['discord username'] || normalizedRow['username'] || '';
                    const pickupLocation = normalizedRow['pickup location'] || normalizedRow['location'] || '';
                    const earliestLeaveTime = normalizedRow['earliest leave time'] || normalizedRow['leave time'] || normalizedRow['time'] || '';
                    const name = normalizedRow['name'] || normalizedRow['real name'] || normalizedRow['first name'] || '';

                    if (!discordUsername && !name) {
                        console.warn('Skipping row without username or name:', row);
                        continue;
                    }

                    parsedRiders.push({
                        id: `rider-${Math.random().toString(36).substr(2, 9)}`,
                        name,
                        discordUsername,
                        pickupLocation,
                        earliestLeaveTime,
                    });
                }

                if (parsedRiders.length === 0) {
                    setError('No valid riders found. Make sure headers are correct.');
                } else {
                    onDataParsed(parsedRiders);
                    setCsvText(''); // Clear input on success
                }
            },
            error: (err: any) => {
                setError(err.message);
            }
        });
    };

    return (
        <div className="bg-white dark:bg-zinc-900 shadow rounded-lg p-6 mb-8 border border-slate-200 dark:border-zinc-800">
            <h2 className="text-xl font-bold mb-4">Import Data</h2>
            <p className="text-sm text-slate-500 mb-4">
                Paste your CSV data below. Ensure your headers match or closely resemble: 
                <strong className="text-slate-800 dark:text-slate-200"> "name"</strong>, 
                <strong className="text-slate-800 dark:text-slate-200"> "discord username"</strong>, 
                <strong className="text-slate-800 dark:text-slate-200"> "pickup location"</strong>, and 
                <strong className="text-slate-800 dark:text-slate-200"> "earliest leave time"</strong>.
            </p>
            <textarea
                className="w-full h-32 p-3 border border-slate-300 dark:border-zinc-700 rounded-md bg-transparent resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
                placeholder="name,discord username,pickup location,earliest leave time&#10;John Doe,user1,Warren,17:00&#10;Jane,user2,ERC,4:00:00 PM"
                value={csvText}
                onChange={(e) => setCsvText(e.target.value)}
            />
            {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
            <button
                onClick={handleParse}
                disabled={!csvText.trim()}
                className="px-4 py-2 bg-slate-900 dark:bg-slate-100 text-white dark:text-zinc-900 rounded-md font-medium hover:bg-slate-800 dark:hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
                Load Riders 
            </button>
        </div>
    );
}
