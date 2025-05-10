# Windows-Float
Windows Float is a lightweight tool to create floating windows that stay on top of other applications. Customize the system tray icon with GIF animations. Runs in the background without taking space in the taskbar. Simple to use and perfect for multitaskers. Requires Python 3.7+.

Windows Float - Floating Window Tool

Features
Create floating windows that stay on top of other applications.
Customizable system tray icon and animations (GIFs).
Lightweight and simple to use.
Runs in the background without taking up space in the taskbar.

Download and Install Dependencies:
Ensure you have Python 3.7+ installed. Download it from the official website.

Install the required Python packages by running the modulesloader.bat, This will install required libraries like pystray, pillow, pyvda, keyboard, and pywin32.

Running the python file:-
edit WindowsFloat.vbs and add the path of python file where ""path/to/the/pythonfile"" is written

GIF Animation: The floating window tool uses windowsfloat.gif for system tray animation. Replace the GIF file if you'd like to change the animation.

Make it a startup file:-
add the WindowsFloat.vbs to the windows startup folder
Open Run (Win + R) and type shell:startup, then press Enter.
Place a shortcut of WindowsFloat.vbs in the Startup folder to have it run when Windows starts.
