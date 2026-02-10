class Kimigas < Formula
  desc "Kimi Code CLI for Gas Town - AI agent for terminal-based development"
  homepage "https://github.com/gastown-publish/kimigas"
  license "Apache-2.0"
  version "0.1.0"

  on_macos do
    on_arm do
      url "https://github.com/gastown-publish/kimigas/releases/download/v#{version}/kimigas-#{version}-aarch64-apple-darwin.tar.gz"
      # sha256 will be updated by release workflow
    end
  end

  on_linux do
    on_intel do
      url "https://github.com/gastown-publish/kimigas/releases/download/v#{version}/kimigas-#{version}-x86_64-unknown-linux-gnu.tar.gz"
    end

    on_arm do
      url "https://github.com/gastown-publish/kimigas/releases/download/v#{version}/kimigas-#{version}-aarch64-unknown-linux-gnu.tar.gz"
    end
  end

  def install
    bin.install "kimi" => "kimigas"
    # Also install as 'kimi' for upstream compatibility
    bin.install_symlink "kimigas" => "kimi"
  end

  test do
    assert_match "kimigas", shell_output("#{bin}/kimigas --version 2>&1", 0)
  end
end
