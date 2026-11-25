type Props = { onClick: () => void; label: string };

const Button = ({ onClick, label }: Props) => <button onClick={onClick}>{label}</button>;

export default Button;
