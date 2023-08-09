from . import app


def main():
    # FIXME to define in a config file
    repositories = [
        "OCA/server-env",
        "OCA/server-tools",
        "OCA/server-ux",
        "OCA/wms",
    ]
    branches_matrix = [
        ("14.0", "15.0"),
        ("15.0", "16.0"),
    ]
    app.App(repositories, branches_matrix).run()


if __name__ == '__main__':
    main()
