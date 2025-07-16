package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "GOOD")
}

func killHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "KILL")
	os.Exit(0) // Exit the server process
}

func main() {
	// Add a 1-second delay before starting the server
	// This simulates a service that takes time to start up
	time.Sleep(1 * time.Second)

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/kill", killHandler)

	// if arg is set, get it as the port
	port := "8080"
	if len(os.Args) > 1 {
		port = os.Args[1]
	}

	fmt.Println("Starting HTTP server on port", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
