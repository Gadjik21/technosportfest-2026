import { useEffect, useState } from "react";

export function App() {
  const [apiStatus, setApiStatus] = useState("Подключаемся…");

  useEffect(() => {
    fetch("/health")
      .then((response) => {
        if (!response.ok) throw new Error();
        setApiStatus("Сервис доступен");
      })
      .catch(() => setApiStatus("Сервис временно недоступен"));
  }, []);

  return (
    <main>
      <h1>ТехноСпортФест 2026</h1>
      <p>Соревнования, результаты и рейтинг спортсменов Дагестана.</p>
      <p>{apiStatus}</p>
    </main>
  );
}
