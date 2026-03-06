"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { createSavedSearch } from "@/lib/api";
import {
  Borough,
  NotificationChannel,
  type ListingFilters,
  type SavedSearch,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const BOROUGHS = Object.values(Borough);
const BEDROOMS = [0, 1, 2, 3, 4] as const;
const CHANNELS: { value: NotificationChannel; label: string }[] = [
  { value: "push", label: "Push" },
  { value: "email", label: "Email" },
  { value: "sse", label: "In-App" },
];

interface CreateSearchDialogProps {
  onCreated: (search: SavedSearch) => void;
  children: React.ReactNode;
}

export function CreateSearchDialog({
  onCreated,
  children,
}: CreateSearchDialogProps) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [priceRange, setPriceRange] = useState<[number, number]>([500, 10000]);
  const [bedrooms, setBedrooms] = useState<number[]>([]);
  const [boroughs, setBoroughs] = useState<Borough[]>([]);
  const [notify, setNotify] = useState(true);
  const [channels, setChannels] = useState<NotificationChannel[]>(["sse"]);

  const reset = () => {
    setStep(0);
    setName("");
    setPriceRange([500, 10000]);
    setBedrooms([]);
    setBoroughs([]);
    setNotify(true);
    setChannels(["sse"]);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const filters: ListingFilters = {};
      if (priceRange[0] > 500) filters.price_min = priceRange[0];
      if (priceRange[1] < 10000) filters.price_max = priceRange[1];
      if (bedrooms.length) filters.bedrooms = bedrooms;
      if (boroughs.length) filters.boroughs = boroughs;

      const search = await createSavedSearch({
        name,
        filters,
        notify,
        channels: notify ? channels : [],
      });
      onCreated(search);
      setOpen(false);
      reset();
    } catch {
      // error handled by API client
    } finally {
      setSaving(false);
    }
  };

  const canNext =
    step === 0
      ? name.trim().length > 0
      : step === 1
        ? true
        : !notify || channels.length > 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {step === 0 && "Name Your Search"}
            {step === 1 && "Set Filters"}
            {step === 2 && "Notifications"}
          </DialogTitle>
          <DialogDescription>
            Step {step + 1} of 3
          </DialogDescription>
        </DialogHeader>

        {step === 0 && (
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Search Name</Label>
              <Input
                placeholder="e.g. Brooklyn 1BR under $2500"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-5 py-2">
            {/* Price */}
            <div className="space-y-3">
              <Label className="text-sm">Price Range</Label>
              <Slider
                min={500}
                max={10000}
                step={100}
                value={priceRange}
                onValueChange={(v) => setPriceRange(v as [number, number])}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>${priceRange[0].toLocaleString()}</span>
                <span>${priceRange[1].toLocaleString()}</span>
              </div>
            </div>

            {/* Bedrooms */}
            <div className="space-y-2">
              <Label className="text-sm">Bedrooms</Label>
              <div className="flex gap-1.5">
                {BEDROOMS.map((n) => {
                  const active = bedrooms.includes(n);
                  return (
                    <Badge
                      key={n}
                      variant={active ? "default" : "outline"}
                      className={cn("cursor-pointer px-3 py-1", active && "ring-1 ring-primary")}
                      onClick={() =>
                        setBedrooms(
                          active
                            ? bedrooms.filter((b) => b !== n)
                            : [...bedrooms, n],
                        )
                      }
                    >
                      {n === 0 ? "Studio" : `${n}BR`}
                    </Badge>
                  );
                })}
              </div>
            </div>

            {/* Boroughs */}
            <div className="space-y-2">
              <Label className="text-sm">Borough</Label>
              <div className="space-y-1.5">
                {BOROUGHS.map((b) => (
                  <div key={b} className="flex items-center gap-2">
                    <Checkbox
                      id={`wiz-borough-${b}`}
                      checked={boroughs.includes(b)}
                      onCheckedChange={(c) =>
                        setBoroughs(
                          c
                            ? [...boroughs, b]
                            : boroughs.filter((x) => x !== b),
                        )
                      }
                    />
                    <Label htmlFor={`wiz-borough-${b}`} className="text-sm font-normal">
                      {b}
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 py-2">
            <div className="flex items-center justify-between">
              <Label>Enable Notifications</Label>
              <Switch checked={notify} onCheckedChange={setNotify} />
            </div>
            {notify && (
              <div className="space-y-2">
                <Label className="text-sm">Channels</Label>
                {CHANNELS.map((ch) => (
                  <div key={ch.value} className="flex items-center gap-2">
                    <Checkbox
                      id={`ch-${ch.value}`}
                      checked={channels.includes(ch.value)}
                      onCheckedChange={(c) =>
                        setChannels(
                          c
                            ? [...channels, ch.value]
                            : channels.filter((x) => x !== ch.value),
                        )
                      }
                    />
                    <Label htmlFor={`ch-${ch.value}`} className="text-sm font-normal">
                      {ch.label}
                    </Label>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          {step > 0 && (
            <Button variant="outline" onClick={() => setStep(step - 1)}>
              Back
            </Button>
          )}
          {step < 2 ? (
            <Button disabled={!canNext} onClick={() => setStep(step + 1)}>
              Next
            </Button>
          ) : (
            <Button disabled={!canNext || saving} onClick={handleSave}>
              {saving ? "Saving..." : "Create Search"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
