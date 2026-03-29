import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.tsx";
import { AuthProvider } from "./context/AuthContext.tsx";
import { Navbar } from "./components/Navbar.tsx";
import './Main.css'

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        {/* <Navbar/> */}
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
