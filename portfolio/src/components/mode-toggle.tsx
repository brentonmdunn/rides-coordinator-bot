import { Moon, Sun, Monitor } from "lucide-react"
import { Button } from "./ui/button"
import { useTheme } from "./use-theme"

export function ModeToggle() {
    const { setTheme, theme } = useTheme()

    return (
        <div className="flex items-center gap-1 p-1 bg-muted rounded-lg border border-border">
            <Button
                variant="ghost"
                size="icon"
                onClick={() => setTheme("light")}
                className={`h-8 w-8 rounded-md transition-all ${theme === "light"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
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
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
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
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                    }`}
                title="Dark Mode"
            >
                <Moon className="h-4 w-4" />
                <span className="sr-only">Dark</span>
            </Button>
        </div>
    )
}
