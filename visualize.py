import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import os

# ARC standard color map
# 0:black, 1:blue, 2:red, 3:green, 4:yellow, 5:grey, 6:magenta, 7:orange, 8:cyan, 9:maroon
ARC_COLORS = [
    "#000000",  # 0: Black
    "#0074D9",  # 1: Blue
    "#FF4136",  # 2: Red
    "#2ECC40",  # 3: Green
    "#FFDC00",  # 4: Yellow
    "#AAAAAA",  # 5: Grey
    "#F012BE",  # 6: Magenta
    "#FF851B",  # 7: Orange
    "#7FDBFF",  # 8: Cyan
    "#870C25",  # 9: Maroon
]

def plot_grid(ax, grid, title):
    """
    Plot a single grid on the given axis.
    """
    if grid is None:
        ax.text(0.5, 0.5, "Invalid / No Output", 
                horizontalalignment='center', verticalalignment='center', 
                transform=ax.transAxes, fontsize=12, color='red')
        ax.set_title(title)
        ax.axis('off')
        return

    try:
        # Handle case where grid might be jagged or not a list of lists
        if isinstance(grid, list) and len(grid) > 0 and isinstance(grid[0], list):
             # Check if all rows have same length, if not, pad or error? 
             # For visualization, let's try to convert directly.
             pass
        
        grid_np = np.array(grid)
        if grid_np.ndim != 2:
             raise ValueError("Not a 2D grid")
             
        height, width = grid_np.shape
    except Exception as e:
        ax.text(0.5, 0.5, f"Format Error\n{str(e)}", 
                horizontalalignment='center', verticalalignment='center', 
                transform=ax.transAxes, fontsize=10, color='red')
        ax.set_title(title)
        ax.axis('off')
        return

    cmap = mcolors.ListedColormap(ARC_COLORS)
    bounds = list(range(11))
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # Plot the grid
    ax.imshow(grid_np, cmap=cmap, norm=norm)
    
    # Draw grid lines
    # We want lines between pixels. 
    # Pixels are centered at 0, 1, 2... 
    # Boundaries are at -0.5, 0.5, 1.5...
    
    # Vertical lines
    for x in np.arange(0.5, width, 1):
        ax.axvline(x, color='#555555', linestyle='-', linewidth=1)
    
    # Horizontal lines
    for y in np.arange(0.5, height, 1):
        ax.axhline(y, color='#555555', linestyle='-', linewidth=1)
    
    # Remove ticks
    ax.set_xticks([])
    ax.set_yticks([])
    
    # Border
    for spine in ax.spines.values():
        spine.set_edgecolor('#555555')
        spine.set_linewidth(2)

    ax.set_title(title, fontsize=14, pad=10)

def save_comparison(pred_grid, gt_grid, file_path):
    """
    Save a comparison image of Prediction vs Ground Truth.
    """
    # Create a figure with 2 subplots
    fig, axes = plt.subplots(1, 2, figsize=(8, 4))
    
    # Plot Ground Truth (Left)
    plot_grid(axes[0], gt_grid, "Ground Truth")
    
    # Plot Prediction (Right)
    plot_grid(axes[1], pred_grid, "Prediction")
    
    plt.tight_layout()
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    plt.savefig(file_path, bbox_inches='tight', dpi=100)
    plt.close(fig)
