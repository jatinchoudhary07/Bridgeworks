import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { CustomThemeProvider, UserProvider, PresenceProvider } from "./contexts";
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <CustomThemeProvider>
          <UserProvider>
            <PresenceProvider>
              <App />
            </PresenceProvider>
          </UserProvider>
        </CustomThemeProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
);
