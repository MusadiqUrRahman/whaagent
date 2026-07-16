package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/rs/zerolog"
)

const (
	defaultConfigPath = ".whaagent.yaml"
	parentConfigPath  = "../.whaagent.yaml"
)

func main() {
	// Setup structured logging
	logger := setupLogger()

	// Get config path from environment or use default
	configPath := os.Getenv("whaagent_CONFIG")
	if configPath == "" {
		configPath = defaultConfigPath
		// If config not found in current dir, try parent directory
		if _, err := os.Stat(configPath); os.IsNotExist(err) {
			if _, parentErr := os.Stat(parentConfigPath); parentErr == nil {
				configPath = parentConfigPath
				logger.Info().Str("config", configPath).Msg("Config not found in current directory, using parent")
			}
		}
	}

	logger.Info().Str("config", configPath).Msg("Loading configuration")

	// Load configuration
	config, err := LoadConfig(configPath)
	if err != nil {
		logger.Fatal().Err(err).Msg("Failed to load configuration")
	}

	// Validate configuration
	if err := config.Validate(); err != nil {
		logger.Fatal().Err(err).Msg("Invalid configuration")
	}

	logger.Info().
		Str("api_host", config.API.Host).
		Int("api_port", config.API.Port).
		Str("storage_base_path", config.Storage.BasePath).
		Msg("Configuration loaded successfully")

	// Print loaded tenants
	logger.Info().Int("count", len(config.WhatsApp.Tenants)).Msg("Loaded WhatsApp tenants")
	for _, tenant := range config.WhatsApp.Tenants {
		logger.Info().
			Str("id", tenant.ID).
			Str("phone", tenant.Phone).
			Str("default_agent", tenant.DefaultAgent).
			Int("allowed_contacts", len(tenant.AllowedContacts)).
			Msg("Tenant")
	}

	// Initialize session manager
	sm, err := NewSessionManager(config, logger)
	if err != nil {
		logger.Fatal().Err(err).Msg("Failed to create session manager")
	}

	// Auto-start sessions for all configured tenants
	ctx := context.Background()
	for _, tenant := range config.WhatsApp.Tenants {
		if err := sm.StartSession(ctx, tenant.ID); err != nil {
			logger.Error().Err(err).Str("tenant_id", tenant.ID).Msg("Failed to start session")
		}
	}

	// Setup graceful shutdown
	setupGracefulShutdown(logger, sm)
}

func setupLogger() zerolog.Logger {
	// Use console writer for human-readable output
	logger := zerolog.New(os.Stdout).With().Timestamp().Logger()

	// Set log level from environment
	logLevel := os.Getenv("LOG_LEVEL")
	if logLevel == "" {
		logLevel = "info"
	}

	level, err := zerolog.ParseLevel(logLevel)
	if err != nil {
		log.Printf("Invalid log level '%s', using 'info': %v", logLevel, err)
		level = zerolog.InfoLevel
	}

	logger = logger.Level(level)

	return logger
}

func setupGracefulShutdown(logger zerolog.Logger, sm *SessionManager) {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	sig := <-sigChan
	logger.Info().Str("signal", sig.String()).Msg("Received shutdown signal")

	if err := sm.StopAll(context.Background()); err != nil {
		logger.Error().Err(err).Msg("Failed to stop sessions")
	}

	logger.Info().Msg("Gateway shutdown complete")
	os.Exit(0)
}

func getAPIURL(config *Config) string {
	return fmt.Sprintf("http://%s:%d", config.API.Host, config.API.Port)
}
