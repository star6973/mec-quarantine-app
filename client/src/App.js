import './App.css';
import Inspection from "./Inspection";

function App() {
  return (
    <div className="App">
      <div className="app_controller">
        <div className="inspection_controller">
          <h1>Inspection Mode</h1>
          <Inspection />
        </div>
        <div className="quarantine_controller">
          <h1>Quarantine Mode</h1>
        </div>
      </div>
    </div>
  );
}

export default App;
