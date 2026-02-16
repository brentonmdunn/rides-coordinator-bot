import { Moon, Sun, Monitor } from "lucide-react"
import { Button } from "./ui/button"
import { useTheme } from "./use-theme"

export function ModeToggle() {
    const { setTheme, theme } = useTheme()

    return (
        <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-zinc-800 rounded-lg border border-slate-200 dark:border-zinc-700">
            <Button
                variant="ghost"
                size="icon"
                onClick={() => setTheme("light")}
                className={`h-8 w-8 rounded-md transition-all ${theme === "light"
                    ? "bg-white text-slate-900 shadow-sm dark:bg-zinc-600 dark:text-slate-100"
                    : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                    }`}
                title="Light Mode"
            >
                <Sun className="h-4 w-4" />
                <span className="sr-only">Light</span>
            </Button>
            <Button
                variant="ghost"
                size="icon"
                onClick={() => setTheme("system")}
                className={`h-8 w-8 rounded-md transition-all ${theme === "system"
                    ? "bg-white text-slate-900 shadow-sm dark:bg-zinc-600 dark:text-slate-100"
                    : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                    }`}
                title="System (Auto)"
            >
                <Monitor className="h-4 w-4" />
                <span className="sr-only">System</span>
            </Button>
            <Button
                variant="ghost"
                size="icon"
                onClick={() => setTheme("dark")}
                className={`h-8 w-8 rounded-md transition-all ${theme === "dark"
                    ? "bg-white text-slate-900 shadow-sm dark:bg-zinc-600 dark:text-slate-100"
                    : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                    }`}
                title="Dark Mode"
            >
                <Moon className="h-4 w-4" />
                <span className="sr-only">Dark</span>
            </Button>
        </div>
    )
}
