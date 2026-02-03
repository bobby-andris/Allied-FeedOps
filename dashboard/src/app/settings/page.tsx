import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { Database, Key, Bell, Shield } from "lucide-react"

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Configure dashboard preferences and integrations
        </p>
      </div>

      <div className="space-y-6">
        {/* Database Connection */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Database Connection
            </CardTitle>
            <CardDescription>
              Supabase connection status and configuration
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Connection Status</p>
                <p className="text-sm text-muted-foreground">Supabase project: qezuszwufortkiutlhym</p>
              </div>
              <Badge className="bg-green-100 text-green-800">Connected</Badge>
            </div>
            <Separator />
            <div className="space-y-2">
              <Label htmlFor="supabase-url">Supabase URL</Label>
              <Input 
                id="supabase-url" 
                value="https://qezuszwufortkiutlhym.supabase.co" 
                disabled 
              />
            </div>
          </CardContent>
        </Card>

        {/* API Keys */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              API Integrations
            </CardTitle>
            <CardDescription>
              External service connections
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Google Merchant Center</p>
                <p className="text-sm text-muted-foreground">Feed sync enabled</p>
              </div>
              <Badge className="bg-green-100 text-green-800">Active</Badge>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Shopify</p>
                <p className="text-sm text-muted-foreground">GraphQL Admin API</p>
              </div>
              <Badge className="bg-green-100 text-green-800">Active</Badge>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Google Analytics</p>
                <p className="text-sm text-muted-foreground">Allied Brass - GA4 (Old)</p>
              </div>
              <Badge className="bg-green-100 text-green-800">Active</Badge>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Google Ads</p>
                <p className="text-sm text-muted-foreground">Customer ID: 6253381786</p>
              </div>
              <Badge className="bg-green-100 text-green-800">Active</Badge>
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5" />
              Notifications
            </CardTitle>
            <CardDescription>
              Configure notification preferences
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Batch completion alerts</p>
                <p className="text-sm text-muted-foreground">Get notified when batches finish publishing</p>
              </div>
              <Switch defaultChecked />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Performance alerts</p>
                <p className="text-sm text-muted-foreground">Alert when performance changes significantly</p>
              </div>
              <Switch defaultChecked />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Error notifications</p>
                <p className="text-sm text-muted-foreground">Get notified of publishing errors</p>
              </div>
              <Switch defaultChecked />
            </div>
          </CardContent>
        </Card>

        {/* Danger Zone */}
        <Card className="border-red-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-600">
              <Shield className="h-5 w-5" />
              Danger Zone
            </CardTitle>
            <CardDescription>
              Irreversible actions
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Clear all approvals</p>
                <p className="text-sm text-muted-foreground">Reset all SKU approval statuses</p>
              </div>
              <Button variant="destructive" size="sm">Clear</Button>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Clear performance data</p>
                <p className="text-sm text-muted-foreground">Remove all performance snapshots</p>
              </div>
              <Button variant="destructive" size="sm">Clear</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
