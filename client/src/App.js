import './App.css';
import Inspection from "./Inspection";
import Quarantine from "./Quarantine";

function App() {
  const status = "quaranting";

  return (
    <div className="App">
      <Quarantine status={status} />
    </div>
  );
}

export default App;