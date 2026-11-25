import Button from "./components/Button";
import * as api from "./lib/api";

export function App() {
  const onClick = () => api.charge(10);
  return <Button onClick={onClick} label="Pay" />;
}
