/**
 * Status bar item - simple button to open the graph panel.
 */

import * as vscode from "vscode";

export class SnipeStatusBar {
  private statusBarItem: vscode.StatusBarItem;

  constructor() {
    this.statusBarItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      100
    );

    // Simple, clear text
    this.statusBarItem.text = "📊 Graph";
    this.statusBarItem.tooltip = "Snipe: Show Repository Graph";

    // Click to open graph panel
    this.statusBarItem.command = "snipe.showGraph";

    // Always visible
    this.statusBarItem.show();
  }

  /**
   * Show the status bar item.
   */
  public show(): void {
    this.statusBarItem.show();
  }

  /**
   * Hide the status bar item.
   */
  public hide(): void {
    this.statusBarItem.hide();
  }

  /**
   * Dispose of the status bar item.
   */
  public dispose(): void {
    this.statusBarItem.dispose();
  }
}
