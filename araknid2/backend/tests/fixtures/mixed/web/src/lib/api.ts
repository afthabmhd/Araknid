export async function charge(amount: number) {
  const res = await fetch("/charge", { method: "POST" });
  return res.json();
}

export interface Charge {
  id: string;
}
