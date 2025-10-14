"""Metrics calculation module for LaTeX projects."""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from pypdf import PdfReader


logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculates word count and page count for LaTeX projects."""

    def __init__(self):
        """Initialize metrics calculator."""
        pass

    def find_main_tex_file(self, project_path: Path) -> Optional[Path]:
        """Find the main .tex file in a project.

        Args:
            project_path: Path to the project directory

        Returns:
            Path to main .tex file or None if not found
        """
        # Common names for main files
        common_names = ["main.tex", "thesis.tex", "paper.tex", "document.tex"]

        for name in common_names:
            tex_file = project_path / name
            if tex_file.exists():
                return tex_file

        # If not found, look for any .tex file
        tex_files = list(project_path.glob("*.tex"))
        if tex_files:
            logger.warning(f"Using first .tex file found: {tex_files[0].name}")
            return tex_files[0]

        return None

    def calculate_word_count(self, project_path: Path) -> Tuple[Optional[int], str]:
        """Calculate word count using texcount.

        Args:
            project_path: Path to the project directory

        Returns:
            Tuple of (word_count, message)
        """
        main_tex = self.find_main_tex_file(project_path)
        if not main_tex:
            return None, "No .tex file found"

        try:
            # Run texcount with merge and sum flags
            # -merge: includes \input and \include files
            # -sum: provides summary
            # -q: quiet mode (less verbose)
            # -1: brief output with just the total
            result = subprocess.run(
                ["texcount", "-merge", "-sum", "-q", "-1", str(main_tex)],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"texcount failed: {result.stderr}")
                return None, f"texcount error: {result.stderr}"

            # Parse the output
            # texcount -1 outputs: "Words in text: XXX"
            output = result.stdout.strip()

            # Try to extract the number
            # Format can be: "1234+567+89 (1890) Header+Body+Float" or just "1234"
            # We want the total in parentheses if available, otherwise the first number
            match = re.search(r'\((\d+)\)', output)
            if match:
                word_count = int(match.group(1))
            else:
                # Try to get the first number
                match = re.search(r'(\d+)', output)
                if match:
                    word_count = int(match.group(1))
                else:
                    return None, f"Could not parse texcount output: {output}"

            logger.info(f"Word count for {project_path.name}: {word_count}")
            return word_count, "Success"

        except subprocess.TimeoutExpired:
            return None, "texcount timed out"
        except FileNotFoundError:
            return None, "texcount not found. Please install TeX Live."
        except Exception as e:
            logger.error(f"Error calculating word count: {str(e)}")
            return None, f"Error: {str(e)}"

    def compile_pdf(self, project_path: Path) -> Tuple[bool, str, Optional[Path]]:
        """Compile LaTeX project to PDF.

        Args:
            project_path: Path to the project directory

        Returns:
            Tuple of (success, message, pdf_path)
        """
        main_tex = self.find_main_tex_file(project_path)
        if not main_tex:
            return False, "No .tex file found", None

        try:
            # Use pdflatex with non-interactive mode
            # -interaction=nonstopmode: don't stop for errors
            # -halt-on-error: stop on first error
            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-file-line-error",
                    main_tex.name
                ],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=120  # 2 minutes timeout
            )

            # Check if PDF was generated
            pdf_path = project_path / main_tex.with_suffix('.pdf').name

            if pdf_path.exists():
                logger.info(f"Successfully compiled {main_tex.name}")
                return True, "Compilation successful", pdf_path
            else:
                # Compilation failed
                error_msg = "Compilation failed"
                # Try to extract error from log
                if "Error" in result.stdout or "!" in result.stdout:
                    lines = result.stdout.split('\n')
                    for i, line in enumerate(lines):
                        if '!' in line or 'Error' in line:
                            error_msg = line.strip()
                            break
                logger.error(f"Compilation failed: {error_msg}")
                return False, error_msg, None

        except subprocess.TimeoutExpired:
            return False, "Compilation timed out", None
        except FileNotFoundError:
            return False, "pdflatex not found. Please install TeX Live.", None
        except Exception as e:
            logger.error(f"Error compiling PDF: {str(e)}")
            return False, f"Error: {str(e)}", None

    def get_page_count_from_pdf(self, pdf_path: Path) -> Tuple[Optional[int], str]:
        """Get page count from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Tuple of (page_count, message)
        """
        try:
            reader = PdfReader(pdf_path)
            page_count = len(reader.pages)
            logger.info(f"Page count for {pdf_path.name}: {page_count}")
            return page_count, "Success"
        except Exception as e:
            logger.error(f"Error reading PDF: {str(e)}")
            return None, f"Error reading PDF: {str(e)}"

    def get_page_count_from_log(self, project_path: Path) -> Tuple[Optional[int], str]:
        """Get page count from LaTeX log file.

        Args:
            project_path: Path to the project directory

        Returns:
            Tuple of (page_count, message)
        """
        main_tex = self.find_main_tex_file(project_path)
        if not main_tex:
            return None, "No .tex file found"

        log_path = project_path / main_tex.with_suffix('.log').name

        if not log_path.exists():
            return None, "Log file not found"

        try:
            with open(log_path, 'r', encoding='latin-1') as f:
                log_content = f.read()

            # Look for "Output written on ... (XX pages"
            match = re.search(r'Output written on .+ \((\d+) pages?', log_content)
            if match:
                page_count = int(match.group(1))
                logger.info(f"Page count from log: {page_count}")
                return page_count, "Success"
            else:
                return None, "Could not find page count in log"

        except Exception as e:
            logger.error(f"Error reading log file: {str(e)}")
            return None, f"Error reading log: {str(e)}"

    def calculate_metrics(self, project_path: Path) -> Tuple[Optional[int], Optional[int], str]:
        """Calculate both word count and page count for a project.

        Args:
            project_path: Path to the project directory

        Returns:
            Tuple of (word_count, page_count, message)
        """
        word_count, word_msg = self.calculate_word_count(project_path)

        # Try to compile PDF
        compile_success, compile_msg, pdf_path = self.compile_pdf(project_path)

        page_count = None
        if compile_success and pdf_path:
            page_count, page_msg = self.get_page_count_from_pdf(pdf_path)

        # If PDF reading failed, try log file
        if page_count is None:
            page_count, page_msg = self.get_page_count_from_log(project_path)

        # Construct status message
        messages = []
        if word_count is not None:
            messages.append(f"Words: {word_count}")
        else:
            messages.append(f"Words: Failed ({word_msg})")

        if page_count is not None:
            messages.append(f"Pages: {page_count}")
        else:
            messages.append("Pages: Failed")

        return word_count, page_count, " | ".join(messages)
